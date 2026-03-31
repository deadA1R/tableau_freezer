import os
import uuid
import datetime
import json
import vertica_python
from dotenv import load_dotenv

from app.report_registry import REPORTS_SQL

load_dotenv()

class TableauFreezer:
    def __init__(self):
        self._init_db()

    def _get_db_connection(self):
        conn_info = {
            'host': os.getenv('VERTICA_HOST', 'localhost'),
            'port': int(os.getenv('VERTICA_PORT', 5433)),
            'user': os.getenv('VERTICA_USER', 'dbadmin'),
            'password': os.getenv('VERTICA_PASSWORD', ''),
            'database': os.getenv('VERTICA_DB', 'docker'),
            'autocommit': True,
        }
        return vertica_python.connect(**conn_info)

    def _init_db(self):
        schema = os.getenv('VERTICA_SCHEMA', 'DM')
        try:
            with self._get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(f"""
                        CREATE TABLE IF NOT EXISTS {schema}.FREEZE_WORKFLOW (
                            TASK_ID VARCHAR(50),
                            REPORT_NAME VARCHAR(255),
                            PERIOD VARCHAR(100),
                            INIT_USER VARCHAR(100),
                            APPROVER_USER VARCHAR(100),
                            STATUS VARCHAR(20) DEFAULT 'PENDING',
                            PARAMS_JSON LONG VARCHAR,
                            COMMENT VARCHAR(500),
                            DATE_CREATE TIMESTAMP,
                            DATE_APPROVE TIMESTAMP
                        )
                    """)
        except Exception as e:
            print(f"Failed to initialize Vertica DB table: {e}")

    def create_request(self, data: dict):
        schema = os.getenv('VERTICA_SCHEMA', 'DM')
        try:
            report = data.get('dashboard', 'Unknown')
            params = data.get('params', {})
            d_s = params.get('DateStart') or params.get('Дата начала периода') or "all"
            d_e = params.get('DateEnd') or params.get('Дата окончания периода') or "all"
            period_key = f"{d_s}_{d_e}"
            approver = data.get('approver', 'tabladmin') 
            initiator = data.get('user', 'unknown')

            with self._get_db_connection() as conn:
                with conn.cursor() as cursor:
                    # Check if a pending request already exists for this period
                    cursor.execute(
                        f"SELECT STATUS FROM {schema}.FREEZE_WORKFLOW WHERE PERIOD = %s AND INIT_USER = %s AND APPROVER_USER = %s AND STATUS = 'PENDING'", 
                        (period_key,initiator, approver)
                    )
                    exists = cursor.fetchone()
                
                    if exists:
                        return {"status": "exists", "message": "Запрос уже на голосовании"}

                    task_id = str(uuid.uuid4())[:8]
                    
                    if initiator == approver:
                        if initiator != "tabladmin":
                            return {
                                "success": False, 
                                "message": "Ошибка безопасности: Инициатор и Аппрувер не могут совпадать."
                            }
                    
                    # Insert the new task
                    cursor.execute(f"""
                        INSERT INTO {schema}.FREEZE_WORKFLOW (
                            TASK_ID, REPORT_NAME, PERIOD, INIT_USER, 
                            APPROVER_USER, PARAMS_JSON, COMMENT, DATE_CREATE
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        task_id, report, period_key, initiator, 
                        approver, json.dumps(params), 
                        data.get('comment', ''),
                        datetime.datetime.now().isoformat()
                    ))
                    # Note: conn.commit() is omitted because 'autocommit': True is set in _get_db_connection
                
            return {"status": "created", "task_id": task_id, "approver": approver}
        except Exception as e:
            print(f"Error: {e}")
            raise e

    def final_approve(self, task_id: str, current_user: str):
        schema = os.getenv('VERTICA_SCHEMA', 'DM')
        try:
            with self._get_db_connection() as conn:
                with conn.cursor('dict') as cursor:
                    cursor.execute(f"SELECT * FROM {schema}.FREEZE_WORKFLOW WHERE TASK_ID = %s", (task_id,))
                    task = cursor.fetchone()

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
                    cursor.execute(f"""
                        INSERT INTO {schema}.FROZEN_DATA_DETAILED_REPORT
                        {final_sql}
                    """)
                    print(f"✅ Заморозка выполнена для {db_name}")

                    cursor.execute(
                        f"UPDATE {schema}.FREEZE_WORKFLOW SET STATUS = 'APPROVED', DATE_APPROVE = %s WHERE TASK_ID = %s", 
                        (datetime.datetime.now(), task_id)
                    )
            
                    return {"success": True}

        except Exception as e:
            print(f"КРИТИЧЕСКАЯ ОШИБКА В final_approve: {e}")
            return {"success": False, "message": str(e)}



    def _build_vertica_sql(self, task, base_sql):
        import json
        from datetime import datetime as dt

        params = json.loads(task['PARAMS_JSON'])
        sql_template = base_sql.get("template")
        tool_code = base_sql.get("tool_code")
        d_start_raw = params.get('Дата начала периода', '01.01.2025')
        d_end_raw = params.get('Дата окончания периода', '30.01.2025')

        # Конвертируем формат DD.MM.YYYY -> YYYY-MM-DD
        try:
            date_start = dt.strptime(d_start_raw, '%d.%m.%Y').strftime('%Y-%m-%d')
            date_end = dt.strptime(d_end_raw, '%d.%m.%Y').strftime('%Y-%m-%d')
        except ValueError:
            # Если вдруг пришло уже в YYYY-MM-DD или другом формате, оставляем как есть
            date_start = d_start_raw
            date_end = d_end_raw

        snapshot_id = task['TASK_ID']
        init_user = task['INIT_USER']
        approver_user = task['APPROVER_USER']

        final_query = sql_template.replace("{ToolCode}", str(tool_code)).replace("{DateStart}", date_start).replace("{DateEnd}", date_end).replace("{SnapshotID}",snapshot_id).replace("{InitUser}",init_user).replace("{ApproverUser}",approver_user)
        
        return final_query

    def get_user_tasks(self, username: str):
        schema = os.getenv('VERTICA_SCHEMA', 'DM')
        with self._get_db_connection() as conn:
            with conn.cursor('dict') as cursor:
                cursor.execute(
                    f"SELECT * FROM {schema}.FREEZE_WORKFLOW WHERE APPROVER_USER = %s AND STATUS = 'PENDING'", 
                    (username,)
                )
                res = cursor.fetchall()

                # Ensure datetime objects are converted to strings if needed for JSON serialization downstream
                for r in res:
                    if r.get('DATE_CREATE'): r['DATE_CREATE'] = str(r['DATE_CREATE'])
                    if r.get('DATE_APPROVE'): r['DATE_APPROVE'] = str(r['DATE_APPROVE'])
                return res