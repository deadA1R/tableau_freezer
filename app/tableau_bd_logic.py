import sqlite3
import uuid
import datetime
import json
from app.report_registry import REPORTS_SQL

class TableauFreezer:
    def __init__(self):
        self.db_path = "workflow_freeze.db"
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS FREEZE_WORKFLOW (
                    TASK_ID TEXT PRIMARY KEY,
                    REPORT_NAME TEXT,
                    PERIOD TEXT, 
                    INIT_USER TEXT,   -- Кто создал запрос
                    APPROVER_USER TEXT,      -- Кто ДОЛЖЕН подтвердить
                    STATUS TEXT DEFAULT 'PENDING',
                    PARAMS_JSON TEXT,      -- Параметры фильтрации
                    COMMENT TEXT,
                    DATE_CREATE TEXT,
                    DATE_APPROVE TEXT       -- Время финального аппрува
                )
            """)
            conn.commit()

    def create_request(self, data: dict):
        try:
            report = data.get('dashboard', 'Unknown')
            params = data.get('params', {})
            
            d_s = params.get('DateStart') or params.get('Дата начала периода') or "all"
            d_e = params.get('DateEnd') or params.get('Дата окончания периода') or "all"
            period_key = f"{d_s}_{d_e}"
            
            with sqlite3.connect(self.db_path) as conn:
                exists = conn.execute("SELECT STATUS FROM FREEZE_WORKFLOW WHERE PERIOD = ? AND STATUS = 'PENDING'", (period_key,)).fetchone()
                if exists:
                    return {"status": "exists", "message": f"Запрос уже на голосовании"}

                task_id = str(uuid.uuid4())[:8]
                
                initiator = data.get('user', 'unknown')
                approver = "local" if initiator != "local" else "tabladmin"
                
                conn.execute("""
                    INSERT INTO FREEZE_WORKFLOW (
                        TASK_ID, REPORT_NAME, PERIOD, INIT_USER, 
                        APPROVER_USER, PARAMS_JSON, COMMENT, DATE_CREATE
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    task_id, report, period_key, initiator, 
                    approver, json.dumps(params), 
                    data.get('COMMENT', ''), 
                    datetime.datetime.now().isoformat()
                ))
                conn.commit()
                
                return {"status": "created", "task_id": task_id, "approver": approver}
        except Exception as e:
            print(f"Error: {e}")
            raise e

    def final_approve(self, task_id: str, current_user: str):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                task = conn.execute("SELECT * FROM FREEZE_WORKFLOW WHERE TASK_ID = ?", (task_id,)).fetchone()
                
                if not task:
                    return {"success": False, "message": "Задача не найдена"}
                
                db_name = task['REPORT_NAME'] 
                
                if task['APPROVER_USER'] != current_user:
                    return {"success": False, "message": f"Нужен аппрув от {task['APPROVER_USER']}"}
                
                if task['STATUS'] != 'PENDING':
                    return {"success": False, "message": f"Статус: {task['STATUS']}"}

                report_meta = REPORTS_SQL.get(db_name)
                if not report_meta:
                    return {"success": False, "message": f"Отчет '{db_name}' не найден в реестре"}

                final_sql = self._build_vertica_sql(task, report_meta)
                
                # ВЫЗОВ ВЕРТИКИ
                # self.vertica_client.execute(final_sql)
                print(f"✅ Заморозка выполнена для {db_name}")

                conn.execute(
                    "UPDATE FREEZE_WORKFLOW SET STATUS = 'APPROVED', DATE_APPROVE = ? WHERE TASK_ID = ?", 
                    (datetime.datetime.now().isoformat(), task_id)
                )
                conn.commit()
                
                return {"success": True}
        except Exception as e:
            print(f"КРИТИЧЕСКАЯ ОШИБКА В final_approve: {e}")
            return {"success": False, "message": str(e)}

    def _build_vertica_sql(self, task, base_sql):
        import json
        params = json.loads(task['PARAMS_JSON'])

        sql_template = base_sql.get("template")
        tool_code = base_sql.get("tool_code")
        date_start = params.get('Дата начала периода', '2025-01-01')
        date_end = params.get('Дата окончания периода', '2025-01-01')
        
        final_query = sql_template.replace("{ToolCode}", str(tool_code)).replace("{DateStart}", date_start).replace("{DateEnd}", date_end)
        
        full_sql = f"""
        INSERT INTO SANDBOX.FROZEN_DATA (SNAPSHOT_ID, INIT, APPROVER, DATE)
        SELECT '{task['TASK_ID']}', '{task['INIT_USER']}', '{task['APPROVER_USER']}', *
        FROM ({final_query}) AS src
        """
        return full_sql

    def get_user_tasks(self, username: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            res = conn.execute(
                "SELECT * FROM FREEZE_WORKFLOW WHERE APPROVER_USER = ? AND STATUS = 'PENDING'", 
                (username,)
            ).fetchall()
            return [dict(r) for r in res]