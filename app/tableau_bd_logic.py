import io
import os
import uuid
import json
import vertica_python
from datetime import datetime as dt
import warnings
from typing import Any
from urllib.parse import unquote

import urllib3
import urllib3.exceptions

from app.report_registry import REPORTS_SQL, REPORT_DEPENDENCIES
from app.statuses import WorkflowStatus, RequestResultStatus
from app.config import REPORT_FROZEN_TABLE_MAP, FROZEN_TABLE_FALLBACK ,REPORTS_WITH_REPORT_DATE, REPORT_5_8_NAME, REPORT_5_8_WORKBOOK, REPORT_5_8_WORKSHEET, WORKFLOW_CONTEXT_COLUMNS, WORKFLOW_EXTENDED_COLUMNS

import tableauserverclient as TSC
from dotenv import load_dotenv

load_dotenv()

def _get_frozen_table(report_name: str) -> str:
    """Возвращает имя таблицы заморозки для переданного отчёта."""
    return REPORT_FROZEN_TABLE_MAP.get(report_name, FROZEN_TABLE_FALLBACK)

def _resolve_period_dates(report_name: str, params: dict[str, Any]) -> tuple[str, str]:
    if report_name in REPORTS_WITH_REPORT_DATE:
        report_date_raw = (
            params.get("Дата отчета")
            or params.get("ReportDate")
            or "all"
        )
        d_e = report_date_raw
 
        # Вычисляем 01.01.Year из даты отчёта
        for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
            try:
                date_t = dt.strptime(report_date_raw, fmt)
                print(date_t)
                d_s = f"01.01.{date_t.year}"
                break
            except ValueError:
                print(report_date_raw)
                continue
        else:
            d_s = "all"
 
        return d_s, d_e
    
    d_s = (
        params.get("DateStart")
        or params.get("Дата начала периода")
        or "all"
    )
    d_e = (
        params.get("DateEnd")
        or params.get("Дата окончания периода")
        or "all"
    )
    
    return d_s, d_e

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

def _resolve_required_freeze_task_id(data: dict[str, Any]) -> str:
    freeze_task_id = data.get("freeze_task_id")
    if isinstance(freeze_task_id, str) and freeze_task_id.strip():
        return freeze_task_id.strip()

    event_id = data.get("event_id")
    if isinstance(event_id, str) and event_id.strip():
        return f"UNBOUND:{event_id.strip()}"

    return f"UNBOUND:{uuid.uuid4().hex}"

class TableauFreezer:
    def __init__(self):
        self._tableau_server_url = None
        self._tableau_auth       = None
        self._tableau_server     = None
        self._init_db()
        try:
            self._init_tableau_client()
        except Exception as e:
            print(f"⚠️  [Tableau] Ошибка инициализации клиента: {e}")

    def _init_tableau_client(self):
        """Инициализирует TSC-клиент из переменных окружения.
        Не падает если credentials не заданы — просто оставляет None.
        """
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
 
        self._tableau_server_url = os.getenv('TABLEAU_SERVER_URL')
        token_name  = os.getenv('TABLEAU_TOKEN_NAME')
        token_value = os.getenv('TABLEAU_TOKEN_VALUE')
        site_id     = os.getenv('TABLEAU_SITENAME', '')
 
        if all([self._tableau_server_url, token_name, token_value]):
            self._tableau_auth = TSC.PersonalAccessTokenAuth(
                token_name=token_name,
                personal_access_token=token_value,
                site_id=site_id,
            )
            self._tableau_server = TSC.Server(self._tableau_server_url, use_server_version=True)
            self._tableau_server.add_http_options({'verify': False})
            print("✅ [Tableau] Клиент инициализирован")
        else:
            self._tableau_auth   = None
            self._tableau_server = None
            print("⚠️  [Tableau] Credentials не заданы — выгрузка из Tableau недоступна")

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
                    self._ensure_frozen_summary_table(cursor, schema)
                    self._ensure_frozen_main_currency_table(cursor, schema)
                    self._ensure_frozen_securities_table(cursor, schema)
                    self._ensure_frozen_profitability_summary_table(cursor, schema)
        except Exception as e:
            print(f"Failed to initialize Vertica DB table: {e}")

    def _ensure_frozen_summary_table(self, cursor, schema) -> None:
        """Создаёт таблицу для заморозки сводной формы 5.8."""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS {schema}.FROZEN_SUMMARY_REPORT_PROFITABILITY (
                SNAPSHOT_ID   VARCHAR(50),
                INIT_USER         VARCHAR(100),
                APPROVER_USER      VARCHAR(100),
                FREEZING_PERIOD_START VARCHAR(50),
                FREEZING_PERIOD_END   VARCHAR(50),
                DATE_FREEZE   VARCHAR(50),
                LOAD_DATE     TIMESTAMP,
                NAME_INDICATOR     VARCHAR(50),
                VALUE_INDICATOR     VARCHAR(100)
            )
        """
        )

    def _ensure_frozen_securities_table(self, cursor, schema: str) -> None:
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {schema}.FROZEN_PROFITABILITY_REPORT_SECURITIES (
                "SNAPSHOT_ID"              VARCHAR(50),
                "INIT"                     VARCHAR(100),
                "APPROVER"                 VARCHAR(100),
                "FREEZING_PERIOD_START"    VARCHAR(50),
                "FREEZING_PERIOD_END"      VARCHAR(50),
                "DATE_FREEZE"              DATE,
                "LOAD_DATE"                TIMESTAMP,
                "COUNTERPARTY_NAME_LEGAL"  VARCHAR(500),
                "CPN_RATE"                 NUMERIC(20, 6),
                "CURRENCY_CODE"            VARCHAR(80),
                "DAYS_COUNT"               INTEGER,
                "DM_DATE"                  DATE,
                "END_DATE"                 DATE,
                "END_SUM_FCY"              NUMERIC(20, 6),
                "END_SUM_LCY"              NUMERIC(20, 6),
                "H_LEGAL_ENTITY_ID"        VARCHAR(100),
                "H_ORGANIZATION_ID"        VARCHAR(100),
                "INCOME_FCY"               NUMERIC(20, 6),
                "INCOME_LCY"               NUMERIC(20, 6),
                "INCOME_SUM_FCY"           NUMERIC(20, 6),
                "INCOME_SUM_LCY"           NUMERIC(20, 6),
                "INTEREST_PERIOD"          VARCHAR(100),
                "LIMIT_DEAL_ID"            VARCHAR(100),
                "LOT_ID"                   VARCHAR(100),
                "NUMBER"                   VARCHAR(100),
                "ORGANIZATION_NAME_LEGAL"  VARCHAR(1000),
                "ORGANIZATION_NAME_SHORT"  VARCHAR(400),
                "START_DATE"               DATE,
                "START_SUM_FCY"            NUMERIC(20, 6),
                "START_SUM_LCY"            NUMERIC(20, 6)
            )
        """)

    def _ensure_frozen_profitability_summary_table(self, cursor, schema: str) -> None:
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {schema}.FROZEN_FULL_REPORT_PROFITABILITY (
                SNAPSHOT_ID                         VARCHAR(50),
                INIT                                VARCHAR(100),
                APPROVER                            VARCHAR(100),
                FREEZING_PERIOD_START               VARCHAR(50),
                FREEZING_PERIOD_END                 VARCHAR(50),
                DATE_FREEZE                         DATE,
                LOAD_DATE                           TIMESTAMP,
                "AMOUNT_CLOSE"                      NUMERIC(20, 6),
                "BALANCE_AMOUNT_FCY"                NUMERIC(20, 6),
                "BALANCE_AMOUNT_LCY"                NUMERIC(20, 6),
                "BANK_NAME"                         VARCHAR(600),
                "CURRENCY_CODE"                     VARCHAR(80),
                "DATE_END"                          DATE,
                "DATE_START"                        DATE,
                "DM_DATE"                           DATE,
                "INTEREST_PERIOD"                   INTEGER,
                "INTEREST_RATE"                     NUMERIC(20, 6),
                "LIMIT_DEAL_ID"                     VARCHAR(100),
                "LIMIT_TOOL_CODE"                   VARCHAR(100),
                "LIMIT_TOOL_NAME"                   VARCHAR(255),
                "NOT_INCLUDED_TO_INCOME"            VARCHAR(10),
                "ORGANIZATION_NAME_LEGAL"           VARCHAR(1000),
                "ORGANIZATION_NAME_SHORT"           VARCHAR(400),
                "PARENT_ORGANIZATION_NAME_SHORT"    VARCHAR(255),
                "START_DATE"                        DATE,
                "CURRENCY_CODE (DM_INCOME_SECURITY)" VARCHAR(80),
                "START_SUM_FCY"                     NUMERIC(20, 6),
                "START_SUM_LCY"                     NUMERIC(20, 6),
                "INCOME_FCY"                        NUMERIC(20, 6),
                "INCOME_LCY"                        NUMERIC(20, 6),
                "INCOME_SUM_FCY"                    NUMERIC(20, 6),
                "INCOME_SUM_LCY"                    NUMERIC(20, 6),
                "VALUE (DI_EXCHANGE_RATES_SUKO1)"   NUMERIC(20, 6),
                "VALUE"                             NUMERIC(20, 6)
            )
        """)

    def _ensure_frozen_main_currency_table(self, cursor, schema: str) -> None:
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {schema}.FROZEN_PROFITABILITY_REPORT_MAIN_CURRENCY (
                "SNAPSHOT_ID"                   VARCHAR(50),
                "INIT"                          VARCHAR(100),
                "APPROVER"                      VARCHAR(100),
                "FREEZING_PERIOD_START"         VARCHAR(50),
                "FREEZING_PERIOD_END"           VARCHAR(50),
                "DATE_FREEZE"                   DATE,
                "LOAD_DATE"                     TIMESTAMP,
                "BALANCE_AMOUNT_FCY"            NUMERIC(20, 6),
                "BALANCE_AMOUNT_LCY"            NUMERIC(20, 6),
                "BANK_NAME"                     VARCHAR(600),
                "CURRENCY_CODE"                 VARCHAR(80),
                "DM_DATE"                       DATE,
                "INTEREST_PERIOD"               INTEGER,
                "INTEREST_RATE"                 NUMERIC(20, 6),
                "LIMIT_DEAL_ID"                 VARCHAR(100),
                "LIMIT_TOOL_CODE"               VARCHAR(100),
                "NOT_INCLUDED_TO_INCOME"        VARCHAR(10),
                "ORGANIZATION_NAME_LEGAL"       VARCHAR(1),
                "ORGANIZATION_NAME_SHORT"       VARCHAR(400),
                "VALUE"                         NUMERIC(20, 6),
                "VALUE (DI_EXCHANGE_RATES_SUKO1)" NUMERIC(20, 6)
            )
        """)

    def _ensure_frozen_main_table(self, cursor, schema: str) -> None:
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {schema}.FROZEN_PROFITABILITY_REPORT_MAIN (
                "SNAPSHOT_ID"                   VARCHAR(50),
                "INIT"                          VARCHAR(100),
                "APPROVER"                      VARCHAR(100),
                "FREEZING_PERIOD_START"         VARCHAR(50),
                "FREEZING_PERIOD_END"           VARCHAR(50),
                "DATE_FREEZE"                   DATE,
                "LOAD_DATE"                     TIMESTAMP,
                "AMOUNT_CLOSE"                  NUMERIC(20, 6),
                "BALANCE_AMOUNT_LCY"            NUMERIC(20, 6),
                "BANK_NAME"                     VARCHAR(600),
                "CURRENCY_CODE"                 VARCHAR(80)
                "DATE_END"                      DATE, 
                "DATE_START"                    DATE,
                "DM_DATE"                       DATE,
                "GUAR_PROJ_NAME"                VARCHAR(1000),
                "INTEREST_PERIOD"               INTEGER,
                "INTEREST_RATE"                 NUMERIC(20, 6),
                "LIMIT_DEAL_ID"                 VARCHAR(100),
                "LIMIT_TOOL_CODE"               VARCHAR(50),
                "LIMIT_TOOL_NAME"               VARCHAR(100),
                "NOT_INCLUDED_TO_INCOME"        VARCHAR(10),
                "ORGANIZATION_NAME_LEGAL"       VARCHAR(500),
                "ORGANIZATION_NAME_SHORT"       VARCHAR(400)
            )
        """)

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
            TABLEAU_USER VARCHAR(400),
            DASHBOARD VARCHAR(500),
            PUBLIC_IP_CANDIDATE VARCHAR(50)
        )
    """)
        
    def check_dependencies(
        self, report_name: str, period_key: str
    ) -> dict[str, Any]:
        schema = os.getenv('VERTICA_SCHEMA', 'DM')
        required = REPORT_DEPENDENCIES.get(report_name, [])

        if not required:
            return {
                "has_dependencies": False,
                "all_approved": True,
                "required": [],
                "approved": [],
                "missing": [],
            }

        approved = []
        missing = []

        with self._get_db_connection() as conn:
            with conn.cursor() as cursor:
                for dep in required:
                    row = cursor.execute(
                        """
                        SELECT TASK_ID FROM {schema}.FREEZE_WORKFLOW
                        WHERE REPORT_NAME = ?
                        AND PERIOD = ?
                        AND STATUS = ?
                        LIMIT 1
                        """,
                        (dep, period_key, WorkflowStatus.APPROVED.value),
                    ).fetchone()

                    if row:
                        approved.append(dep)
                    else:
                        missing.append(dep)

        return {
            "has_dependencies": True,
            "all_approved": len(missing) == 0,
            "required": required,
            "approved": approved,
            "missing": missing,
        }

    def create_request(self, data: dict[str, Any]) -> dict[str, Any]:
        schema = os.getenv('VERTICA_SCHEMA', 'DM')
        try:
            report = data.get('dashboard', 'Unknown')
            params = data.get('params', {})
            session_id = data.get("session_id")
            event_id = data.get("event_id")
            event_type = data.get("event_type")
            public_ip_candidate = _extract_public_ip_candidate(data)

            d_s, d_e = _resolve_period_dates(report, params)
            period_key = f"{d_s}_{d_e}"
            approver = data.get('approver', 'tabladmin') 
            initiator = data.get('user', 'unknown')

            dep_check = self.check_dependencies(report, period_key)
            if dep_check["has_dependencies"] and not dep_check["all_approved"]:
                return {
                    "success": False,
                    "status": "DEPENDENCIES_NOT_MET",
                    "message": (
                        f"Невозможно создать задачу: не все обязательные отчёты "
                        f"подтверждены за период {period_key}."
                    ),
                    "dependencies": dep_check,
                }

            with self._get_db_connection() as conn:
                with conn.cursor() as cursor:
                    # Check if a pending request already exists for this period
                    cursor.execute(
                        f"SELECT STATUS, APPROVER_USER FROM {schema}.FREEZE_WORKFLOW WHERE PERIOD = %s AND REPORT_NAME = %s AND INIT_USER = %s AND APPROVER_USER = %s AND STATUS IN (%s, %s)", 
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
                        f"SELECT TASK_ID, SESSION_ID, EVENT_ID, EVENT_TYPE, PUBLIC_IP_CANDIDATE FROM {schema}.FREEZE_WORKFLOW WHERE TASK_ID = %s",
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
                        existing[1]
                        and session_id
                        and existing[1] != session_id
                    ):
                        return {
                            "matched_task": True,
                            "updated": False,
                            "message": "Session mismatch: запись уже привязана к другому session_id",
                        }

                    cursor.execute(
                        f"""
                        UPDATE {schema}.FREEZE_WORKFLOW
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
                        "updated": cursor.rowcount > 0,
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
                        "row_id": cursor.rowcount > 0,
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
                    if task['APPROVER_USER'] != current_user:
                        return {"success": False, "message": f"Нужен аппрув от {task['APPROVER_USER']}"}
                    if task['STATUS'] != WorkflowStatus.PENDING.value:
                        return {"success": False, "message": f"Статус: {task['STATUS']}"}
                    

                    db_name = task['REPORT_NAME'] 

                    report_meta = REPORTS_SQL.get(db_name)
                    if not report_meta:
                        return {"success": False, "message": f"Отчет '{db_name}' не найден в реестре"}

                    final_sql = self._build_vertica_sql(task, report_meta)

                    target_table = _get_frozen_table(db_name)
                    print(f"[freeze] Отчёт: {db_name!r} → таблица: {schema}.{target_table}")
            
                    # ВЫЗОВ ВЕРТИКИ НЕОБХОДИМО ПЕРЕПИСАТЬ ПОЛНОСТЬЮ
                    cursor.execute(f"""
                        INSERT INTO {schema}.{target_table}
                        {final_sql}
                    """)
                    print(f"✅ Заморозка выполнена для {db_name}")

                    cursor.execute(
                        f"UPDATE {schema}.FREEZE_WORKFLOW SET STATUS = %s, DATE_APPROVE = %s WHERE TASK_ID = %s", 
                        (WorkflowStatus.APPROVED.value, dt.now(), task_id)
                    )
            
                    task_dict = dict(task)

        except Exception as e:
            print(f"КРИТИЧЕСКАЯ ОШИБКА В final_approve: {e}")
            return {"success": False, "message": str(e)}
        
        summary_result = None
        if task_dict.get('REPORT_NAME') == REPORT_5_8_NAME:
            print(f"[5.8] Начинаем выгрузку данных из Tableau...")
            try:
                summary_result = self._fetch_and_save_summary_report(task_dict, dt.now())
            except Exception as e:
                summary_result = {"saved": False, "reason": str(e)}
            print(f"[5.8] Результат выгрузки: {summary_result}")

        return {"success": True, "summary_saved": summary_result}



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
    
    def _fetch_and_save_summary_report(self, task: dict[str, Any], approve_ts: str) -> dict[str, Any]:
        """
        Забирает данные листа REPORT_5_8_WORKSHEET из Tableau Server через get_view_data
        и сохраняет строки в FROZEN_SUMMARY_REPORT_PROFITABILITY.
        Вызывается только при аппруве задачи отчёта 5.8.
        """
        if self._tableau_server is None:
            return {"saved": False, "reason": "Tableau Server credentials not configured in .env"}
 
        params = json.loads(task['PARAMS_JSON'])
        d_start, d_end = _resolve_period_dates(task['REPORT_NAME'], params)
 
        tableau_params = {
            'Дата начала периода': d_start,
            'Дата окончания периода': d_end,
        }
 
        target_path = f"{REPORT_5_8_WORKBOOK}/{REPORT_5_8_WORKSHEET}"
        print(f"[5.8] Выгружаем: {target_path!r} | params={tableau_params}")
 
        try:
            df = self.get_view_data(target_path, tableau_params)
            print(f"[5.8] Получено {len(df)} строк, {len(df.columns)} колонок")
            print(df)
            print(f"[5.8] Колонки: {list(df.columns)}")
        except Exception as e:
            return {"saved": False, "reason": f"Ошибка выгрузки из Tableau: {e}"}
 
        return self._save_df_to_summary_table(df, task, d_start, d_end, approve_ts)
    
    def _save_df_to_summary_table(
        self,
        df: "pd.DataFrame",
        task: dict[str, Any],
        d_start: str,
        d_end: str,
        approve_ts: str,
    ) -> dict[str, Any]:
        """Записывает DataFrame построчно в FROZEN_SUMMARY_REPORT_PROFITABILITY."""
        schema = os.getenv('VERTICA_SCHEMA', 'DM')
        try:
            with self._get_db_connection() as conn:
                with conn.cursor() as cursor:
                    # Перезапись — удаляем старый снапшот
                    cursor.execute(
                        f"DELETE FROM {schema}.FROZEN_SUMMARY_REPORT_PROFITABILITY WHERE SNAPSHOT_ID = %s",
                        (task['TASK_ID'],),
                    )
 
                    rows_to_insert = [
                        (
                            task['TASK_ID'],
                            task['INIT_USER'],
                            task['APPROVER_USER'],
                            d_start,
                            d_end,
                            str(approve_ts)[:10],   # DATE_FREEZE  (только дата)
                            str(approve_ts),         # LOAD_DATE    (полный timestamp)
                            str(row.iloc[0]),        # NAME_INDICATOR
                            str(row.iloc[1]),        # VALUE_INDICATOR
                        )
                        for _, row in df.iterrows()
                    ]
 
                    cursor.executemany(
                        f"""
                        INSERT INTO {schema}.FROZEN_SUMMARY_REPORT_PROFITABILITY (
                            SNAPSHOT_ID, INIT_USER, APPROVER_USER,
                            FREEZING_PERIOD_START, FREEZING_PERIOD_END,
                            DATE_FREEZE, LOAD_DATE,
                            NAME_INDICATOR, VALUE_INDICATOR
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        rows_to_insert,
                    )
 
            return {"saved": True, "rows_written": len(df), "snapshot_id": task['TASK_ID']}
        except Exception as e:
            print(f"Ошибка _save_df_to_summary_table: {e}")
            return {"saved": False, "reason": str(e)}

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
                    
                    cursor.execute(query, (WorkflowStatus.VOIDED.value, f" | [ОТЗЫВ {admin_user}: {comment}]", dt.now(), task_id))
                return {"success": True}
        except Exception as e:
            return {"success": False, "message": str(e)}
        
    def get_view_data(self, workbook_name_or_path: str, parameters: dict = None):
        """
        Универсальная выгрузка данных из Tableau Server.
 
        workbook_name_or_path — имя воркбука ИЛИ путь вида "workbook/sheet".
        Если содержит "/", разбивается на workbook-часть и sheet-часть.
        Возвращает pd.DataFrame.
        """
        import pandas as pd
        import requests
 
        if self._tableau_server is None or self._tableau_auth is None:
            raise RuntimeError("Tableau credentials не заданы в .env")
 
        with self._tableau_server.auth.sign_in(self._tableau_auth):
            print(f"[Tableau] Ищу: {repr(workbook_name_or_path)}")
 
            target_sheet_name = None
            search_name = workbook_name_or_path
 
            # Разбиваем путь "workbook/sheet" если есть "/"
            if "/" in workbook_name_or_path:
                parts = unquote(workbook_name_or_path).replace("views/", "").split("/")
                search_name       = parts[0]
                target_sheet_name = parts[-1].split("?")[0]
                print(f"[Tableau]   Воркбук: {repr(search_name)}")
                print(f"[Tableau]   Лист:    {repr(target_sheet_name)}")
 
            # Поиск по Name
            req_options = TSC.RequestOptions()
            req_options.filter.add(TSC.Filter(
                TSC.RequestOptions.Field.Name,
                TSC.RequestOptions.Operator.Equals,
                search_name,
            ))
            workbooks, _ = self._tableau_server.workbooks.get(req_options)
 
            # Фоллбэк — поиск по ContentUrl
            if not workbooks:
                print(f"[Tableau]   По Name не найден, пробую ContentUrl...")
                req_options2 = TSC.RequestOptions()
                req_options2.filter.add(TSC.Filter(
                    TSC.RequestOptions.Field.ContentUrl,
                    TSC.RequestOptions.Operator.Equals,
                    search_name,
                ))
                workbooks, _ = self._tableau_server.workbooks.get(req_options2)
 
            if not workbooks:
                # Для диагностики — печатаем все воркбуки
                all_wbs, _ = self._tableau_server.workbooks.get()
                names = [w.name for w in all_wbs]
                print(f"[Tableau]   Все воркбуки ({len(names)}): {names}")
                raise ValueError(f"Воркбук '{search_name}' не найден на Tableau Server")
 
            wb = workbooks[0]
            print(f"[Tableau]   Найден воркбук: {repr(wb.name)} (id={wb.id})")
            self._tableau_server.workbooks.populate_views(wb)
 
            # Все листы воркбука
            print(f"[Tableau]   Листы ({len(wb.views)}):")
            for v in wb.views:
                print(f"[Tableau]     name={repr(v.name)}  content_url={repr(v.content_url)}")
 
            # Ищем нужный лист
            view_id = None
            if target_sheet_name:
                view = next(
                    (v for v in wb.views
                     if target_sheet_name in (v.content_url or "")
                     or target_sheet_name == v.name),
                    None,
                )
                if view:
                    view_id = view.id
                    print(f"[Tableau]   Используем лист: {repr(view.name)}")
                else:
                    print(f"[Tableau]   ⚠️  Лист {repr(target_sheet_name)} не найден — берём первый")
 
            # Фоллбэк на первый лист
            if not view_id and wb.views:
                view_id = wb.views[0].id
                print(f"[Tableau]   Первый лист: {repr(wb.views[0].name)}")
 
            # REST API запрос данных
            endpoint = (
                f"{self._tableau_server_url}/api/{self._tableau_server.version}"
                f"/sites/{self._tableau_server.site_id}/views/{view_id}/data"
            )
            headers = {'X-Tableau-Auth': self._tableau_server.auth_token}
 
            print(f"[Tableau]   GET {endpoint}")
            print(f"[Tableau]   Params: {parameters}")
 
            resp = requests.get(
                endpoint,
                headers=headers,
                params=parameters,
                verify=False,
                timeout=60,
            )
 
            if resp.status_code != 200:
                raise Exception(
                    f"Ошибка выгрузки ({resp.status_code}): {resp.text[:300]}"
                )
 
            df = pd.read_csv(io.BytesIO(resp.content))
            print(f"[Tableau]   ✅ Получено {len(df)} строк, {len(df.columns)} колонок")
            return df