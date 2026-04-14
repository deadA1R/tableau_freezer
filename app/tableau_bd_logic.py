import os
import uuid
import json
import vertica_python
from dotenv import load_dotenv
from datetime import datetime as dt
import warnings
from typing import Any

from app.report_registry import REPORTS_SQL
from app.statuses import WorkflowStatus, RequestResultStatus

load_dotenv()

def _extract_public_ip_candidate(data: dict[str, Any]) -> str | None:
    top_level_value = data.get("public_ip_candidate")
    if isinstance(top_level_value, str) and top_level_value.strip():
        return top_level_value.strip()

    client_context = data.get("client_context")
    if isinstance(client_context, dict):
        client_value = client_context.get("public_ip_candidate")
        if isinstance(client_value, str) and client_value.strip():
            return client_value.strip()

    return None

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
                            IS_ACTUAL VARCHAR(5) DEFAULT 1,
                            SESSION_ID VARCHAR(100),
                            EVENT_ID VARCHAR(100),
                            EVENT_TYPE VARCHAR(200),
                            PUBLIC_IP_CANDIDATE VARCHAR(50),
                            DATE_CREATE TIMESTAMP,
                            DATE_APPROVE TIMESTAMP,
                            DATE_VOIDED TIMESTAMP
                        )
                    """)
                    self._ensure_workflow_extended_table(cursor, schema)
        except Exception as e:
            print(f"Failed to initialize Vertica DB table: {e}")

    def _ensure_workflow_extended_table(self, cursor, schema: str) -> None:
        cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {schema}.FREEZE_WORKFLOW_EXTENDED (
            FREEZE_TASK_ID VARCHAR(50),
            SESSION_ID VARCHAR(100),
            EVENT_ID VARCHAR(100),
            EVENT_TYPE VARCHAR(200),
            TIMESTAMP_UTC TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            USER_AGENT VARCHAR(500),
            ACCEPT_LANGUAGE VARCHAR(100),
            SEC_CH_UA VARCHAR(255),
            SEC_CH_UA_PLATFORM VARCHAR(100),
            DEVICE_TYPE VARCHAR(50),
            TABLEAU_USER VARCHAR(100),
            DASHBOARD VARCHAR(500),
            PUBLIC_IP_CANDIDATE VARCHAR(50)
        )
    """)

    def create_request(self, data: dict[str, Any]) -> dict[str, Any]:
        schema = os.getenv('VERTICA_SCHEMA', 'DM')
        try:
            report = data.get('dashboard', 'Unknown')
            params = data.get('params', {})
            session_id = data.get("session_id")
            event_id = data.get("event_id")
            event_type = data.get("event_type")
            public_ip_candidate = _extract_public_ip_candidate(data)

            d_s = params.get('DateStart') or params.get('Дата начала периода') or "all"
            d_e = params.get('DateEnd') or params.get('Дата окончания периода') or "all"
            period_key = f"{d_s}_{d_e}"
            approver = data.get('approver', 'tabladmin') 
            initiator = data.get('user', 'unknown')

            with self._get_db_connection() as conn:
                with conn.cursor() as cursor:
                    # Check if a pending request already exists for this period
                    cursor.execute(
                        f"SELECT STATUS, APPROVER_USER, FROM {schema}.FREEZE_WORKFLOW WHERE PERIOD = %s AND REPORT_NAME = %s AND INIT_USER = %s AND APPROVER_USER = %s AND STATUS IN (%s, %s)", 
                        (period_key, report, initiator, approver, WorkflowStatus.PENDING.value, WorkflowStatus.APPROVED.value)
                    )
                    exists = cursor.fetchone()
                
                    if exists:
                        status_msg = (
                        "уже подтвержден"
                        if exists['STATUS'] == WorkflowStatus.APPROVED.value
                        else f"ожидает аппрува от {exists['APPROVER_USER']}"
                    )
                        return {
                            "status": RequestResultStatus.EXISTS,
                            "message": f"Срез за период {period_key} {status_msg}. Чтобы создать новый, старый должен быть аннулирован (VOIDED)."
                        }

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
                            APPROVER_USER, PARAMS_JSON, COMMENT, IS_ACTUAL, SESSION_ID, EVENT_ID, EVENT_TYPE, PUBLIC_IP_CANDIDATE, DATE_CREATE
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        task_id, report, period_key, initiator, 
                        approver, 
                        json.dumps(params), 
                        data.get('comment', ''), 
                        '1', 
                        session_id,
                        event_id,
                        event_type,
                        public_ip_candidate,
                        dt.now().isoformat()
                    ))
                    # Note: conn.commit() is omitted because 'autocommit': True is set in _get_db_connection
                
            return {
                    "status": RequestResultStatus.CREATED,
                    "task_id": task_id,
                    "approver": approver,
                }
        except Exception as e:
            print(f"Error: {e}")
            raise e

    def backfill_request_context(self, task_id: str, context: dict[str, Any]) -> dict[str, Any]:
        schema = os.getenv('VERTICA_SCHEMA', 'DM')
        try:
            session_id = context.get("session_id")
            event_id = context.get("event_id")
            event_type = context.get("event_type")
            public_ip_candidate = _extract_public_ip_candidate(context)

            with self._get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "SELECT TASK_ID, SESSION_ID, EVENT_ID, EVENT_TYPE, PUBLIC_IP_CANDIDATE FROM {schema}.FREEZE_WORKFLOW WHERE TASK_ID = %s",
                        (task_id,),
                    )
                    existing = cursor.fetchone()

                    if not existing:
                        return {
                            "matched_task": False,
                            "updated": False,
                            "message": "Задача для backfill не найдена",
                        }

                    if (
                        existing["SESSION_ID"]
                        and session_id
                        and existing["SESSION_ID"] != session_id
                    ):
                        return {
                            "matched_task": True,
                            "updated": False,
                            "message": "Session mismatch: запись уже привязана к другому session_id",
                        }

                    cursor.execute(
                        """
                        UPDATE FREEZE_WORKFLOW
                        SET SESSION_ID = COALESCE(SESSION_ID, %s),
                            EVENT_ID = COALESCE(EVENT_ID, %s),
                            EVENT_TYPE = COALESCE(EVENT_TYPE, %s),
                            PUBLIC_IP_CANDIDATE = COALESCE(PUBLIC_IP_CANDIDATE, %s)
                        WHERE TASK_ID = %s
                        """,
                        (session_id, event_id, event_type, public_ip_candidate, task_id),
                    )

                    return {
                        "matched_task": True,
                        "updated": conn.total_changes > 0,
                        "message": "Контекст сопоставлен по task_id",
                    }
        except Exception as e:
            print(f"Error: {e}")
            raise e
    
    def insert_workflow_extended_event(self, event_payload: dict[str, Any]) -> dict[str, Any]:
        schema = os.getenv('VERTICA_SCHEMA', 'DM')
        server_context = event_payload.get("server_context") or {}
        client_hints = server_context.get("client_hints") or {}

        try:
            with self._get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        f"""
                        INSERT INTO {schema}.FREEZE_WORKFLOW_EXTENDED (
                            FREEZE_TASK_ID,
                            SESSION_ID,
                            EVENT_ID,
                            EVENT_TYPE,
                            TIMESTAMP_UTC,
                            USER_AGENT,
                            ACCEPT_LANGUAGE,
                            SEC_CH_UA,
                            SEC_CH_UA_PLATFORM,
                            DEVICE_TYPE,
                            TABLEAU_USER,
                            DASHBOARD,
                            PUBLIC_IP_CANDIDATE
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            event_payload.get("freeze_task_id"),
                            event_payload.get("session_id"),
                            event_payload.get("event_id"),
                            event_payload.get("event_type"),
                            server_context.get("timestamp_utc"),
                            server_context.get("user_agent"),
                            server_context.get("accept_language"),
                            client_hints.get("sec_ch_ua"),
                            client_hints.get("sec_ch_ua_platform"),
                            server_context.get("device_type"),
                            event_payload.get("user"),
                            event_payload.get("dashboard"),
                            _extract_public_ip_candidate(event_payload),
                        ),
                    )
                    
                    return {
                        "saved": True,
                        "row_id": cursor.rowcount,
                        "table": f"{schema}.FREEZE_WORKFLOW_EXTENDED"
                    }
        except Exception as e:
            print(f"Error in insert_workflow_extended_event: {e}")
            raise e

    def final_approve(self, task_id: str, current_user: str) -> dict[str, Any]:
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
            
                    if task['STATUS'] != WorkflowStatus.PENDING.value:
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
                        f"UPDATE {schema}.FREEZE_WORKFLOW SET STATUS = %s, DATE_APPROVE = %s WHERE TASK_ID = %s", 
                        (WorkflowStatus.APPROVED.value, dt.now(), task_id)
                    )
            
                    return {"success": True}

        except Exception as e:
            print(f"КРИТИЧЕСКАЯ ОШИБКА В final_approve: {e}")
            return {"success": False, "message": str(e)}



    def _build_vertica_sql(self, task, base_sql: dict[str, Any]) -> str:
        import json

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

    def get_user_tasks(self, username: str) -> list[dict[str, Any]]:
        schema = os.getenv('VERTICA_SCHEMA', 'DM')
        with self._get_db_connection() as conn:
            with conn.cursor('dict') as cursor:
                cursor.execute(
                    f"SELECT * FROM {schema}.FREEZE_WORKFLOW WHERE APPROVER_USER = %s AND STATUS = %s", 
                    (username, WorkflowStatus.PENDING.value)
                )
                res = cursor.fetchall()

                # Ensure datetime objects are converted to strings if needed for JSON serialization downstream
                for r in res:
                    if r.get('DATE_CREATE'): r['DATE_CREATE'] = str(r['DATE_CREATE'])
                    if r.get('DATE_APPROVE'): r['DATE_APPROVE'] = str(r['DATE_APPROVE'])
                return res
            
    def get_approved_tasks(
            self, 
            report_filter: str | None = None, 
            date_filter: str | None = None
        ) -> list[dict[str, Any]]:
        schema = os.getenv('VERTICA_SCHEMA', 'DM')
        query = f"SELECT * FROM {schema}.FREEZE_WORKFLOW WHERE STATUS = %s"
        params = [WorkflowStatus.APPROVED.value]
        
        if report_filter:
            query += " AND REPORT_NAME LIKE %s"
            params.append(f"%{report_filter}%")
        if date_filter:
            query += " AND DATE_APPROVE >= %s"
            params.append(date_filter)
            
        query += " ORDER BY DATE_APPROVE DESC"
        
        with self._get_db_connection() as conn:
            with conn.cursor('dict') as cursor:
                cursor.execute(query, params)
                res = cursor.fetchall()
                
                for r in res:
                    if r.get('DATE_CREATE'): r['DATE_CREATE'] = str(r['DATE_CREATE'])
                    if r.get('DATE_APPROVE'): r['DATE_APPROVE'] = str(r['DATE_APPROVE'])
                return res

    def void_task(self, task_id: str, admin_user: str, comment: str) -> dict[str, Any]:
        schema = os.getenv('VERTICA_SCHEMA', 'DM')
        try:
            with self._get_db_connection() as conn:
                with conn.cursor('dict') as cursor:
                    query = f"""
                        UPDATE {schema}.FREEZE_WORKFLOW 
                        SET STATUS = %s, 
                            IS_ACTUAL = 0,
                            COMMENT = COALESCE(COMMENT, '') || %s,
                            DATE_VOIDED = %s
                        WHERE TASK_ID = %s
                    """
                    
                    cursor.execute(query, (WorkflowStatus.VOIDED.value, f" | [ОТЗЫВ {admin_user}: {comment}]", task_id, dt.now()))
                return {"success": True}
        except Exception as e:
            return {"success": False, "message": str(e)}