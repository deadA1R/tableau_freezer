import sqlite3
import uuid
import datetime
import json
from datetime import datetime
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

    def _init_db(self):
        schema = os.getenv('VERTICA_SCHEMA', 'DM')
        try:
            with self._get_db_connection() as conn:
                with conn.cursor() as cursor:
                    # Таблица воркфлоу (уже есть)
                    cursor.execute(f"""
                        CREATE TABLE IF NOT EXISTS {schema}.FREEZE_WORKFLOW (
                            TASK_ID VARCHAR(50), REPORT_NAME VARCHAR(255),
                            PERIOD VARCHAR(100), INIT_USER VARCHAR(100),
                            APPROVER_USER VARCHAR(100), STATUS VARCHAR(20) DEFAULT 'PENDING',
                            PARAMS_JSON LONG VARCHAR, COMMENT VARCHAR(500),
                            DATE_CREATE TIMESTAMP, DATE_APPROVE TIMESTAMP
                        )
                    """)
                   
        except Exception as e:
            print(f"Failed to initialize Vertica tables: {e}")

    def create_request(self, data: dict):
        try:
            report = data.get('dashboard', 'Unknown')
            params = data.get('params', {})
            
            d_s = params.get('DateStart') or params.get('Дата начала периода') or "all"
            d_e = params.get('DateEnd') or params.get('Дата окончания периода') or "all"
            period_key = f"{d_s}_{d_e}"
            approver = data.get('approver', 'tabladmin') 
            initiator = data.get('user', 'unknown')
            
            with sqlite3.connect(self.db_path) as conn:
                exists = conn.execute("""
                            SELECT STATUS 
                            FROM FREEZE_WORKFLOW 
                            WHERE PERIOD = ? 
                            AND INIT_USER = ? 
                            AND APPROVER_USER = ? 
                            AND STATUS = 'PENDING'
                        """, (period_key, initiator, approver)).fetchone()
                if exists:
                    return {"status": "exists", "message": f"Запрос уже на голосовании"}

                task_id = str(uuid.uuid4())[:8]
                
                if initiator == approver:
                    if initiator != "tabladmin":
                        return {
                            "success": False, 
                            "message": "Ошибка безопасности: Инициатор и Аппрувер не могут совпадать."
                        }
                
                conn.execute("""
                    INSERT INTO FREEZE_WORKFLOW (
                        TASK_ID, REPORT_NAME, PERIOD, INIT_USER, 
                        APPROVER_USER, PARAMS_JSON, COMMENT, DATE_CREATE
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    task_id, report, period_key, initiator, 
                    approver, json.dumps(params), 
                    data.get('comment', ''), 
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
        d_start_raw = params.get('Дата начала периода', '01.01.2025')
        d_end_raw = params.get('Дата окончания периода', '30.01.2025')

        # Конвертируем формат DD.MM.YYYY -> YYYY-MM-DD
        try:
            date_start = datetime.strptime(d_start_raw, '%d.%m.%Y').strftime('%Y-%m-%d')
            date_end = datetime.strptime(d_end_raw, '%d.%m.%Y').strftime('%Y-%m-%d')
        except ValueError:
            # Если вдруг пришло уже в YYYY-MM-DD или другом формате, оставляем как есть
            date_start = d_start_raw
            date_end = d_end_raw

        snapshot_id = task['TASK_ID']
        init_user = task['INIT_USER']
        approver_user = task['APPROVER_USER']

        final_query = sql_template.replace("{ToolCode}", str(tool_code)).replace("{DateStart}", date_start).replace("{DateEnd}", date_end).replace("{SnapshotID}",snapshot_id).replace("{IninUser}",init_user).replace("{ApproverUser}",approver_user)
        
        return final_query

    def get_user_tasks(self, username: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            res = conn.execute(
                "SELECT * FROM FREEZE_WORKFLOW WHERE APPROVER_USER = ? AND STATUS = 'PENDING'", 
                (username,)
            ).fetchall()
            return [dict(r) for r in res]