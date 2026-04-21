import io
import sqlite3
import uuid
import json
import os
import warnings
from datetime import datetime
from typing import Any
from urllib.parse import unquote

import urllib3
import urllib3.exceptions

from app.report_registry import REPORTS_SQL, REPORT_DEPENDENCIES
from app.statuses import WorkflowStatus, RequestResultStatus
from app.config import REPORTS_WITH_REPORT_DATE, REPORT_5_8_NAME, REPORT_5_8_WORKBOOK, REPORT_5_8_WORKSHEET, WORKFLOW_CONTEXT_COLUMNS, WORKFLOW_EXTENDED_COLUMNS

import tableauserverclient as TSC

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
                date_t = datetime.strptime(report_date_raw, fmt)
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
        self.db_path = "workflow_freeze.db"
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
                    IS_ACTUAL INTEGER DEFAULT 1,
                    SESSION_ID TEXT,
                    EVENT_ID TEXT,
                    EVENT_TYPE TEXT,
                    PUBLIC_IP_CANDIDATE TEXT,
                    DATE_CREATE TEXT,
                    DATE_APPROVE TEXT       -- Время финального аппрува
                )
            """)
            self._ensure_workflow_context_columns(conn)
            self._ensure_workflow_extended_table(conn)
            self._ensure_frozen_summary_table(conn)
            conn.commit()

    def _ensure_frozen_summary_table(self, conn: sqlite3.Connection) -> None:
        """Создаёт таблицу для заморозки сводной формы 5.8."""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS FROZEN_SUMMARY_REPORT_PROFITABILITY (
                SNAPSHOT_ID   TEXT PRIMARY KEY,
                INIT          TEXT,
                APPROVER      TEXT,
                FREEZING_PERIOD_START TEXT,
                FREEZING_PERIOD_END   TEXT,
                DATE_FREEZE   TEXT,
                LOAD_DATE     TEXT,
                DATA_JSON     TEXT   -- JSON одной строки; заменим на явные колонки после RDP
            )
        """
        )

    def _ensure_workflow_context_columns(self, conn: sqlite3.Connection) -> None:
        existing_columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(FREEZE_WORKFLOW)").fetchall()
        }

        for column_name, column_type in WORKFLOW_CONTEXT_COLUMNS.items():
            if column_name not in existing_columns:
                conn.execute(
                    f"ALTER TABLE FREEZE_WORKFLOW ADD COLUMN {column_name} {column_type}"
                )

    def _ensure_workflow_extended_table(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS freeze_workflow_extended (
                FREEZE_TASK_ID TEXT NOT NULL,
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                SESSION_ID TEXT,
                EVENT_ID TEXT,
                EVENT_TYPE TEXT,
                TIMESTAMP_UTC TEXT,
                USER_AGENT TEXT,
                ACCEPT_LANGUAGE TEXT,
                SEC_CH_UA TEXT,
                SEC_CH_UA_PLATFORM TEXT,
                DEVICE_TYPE TEXT,
                TABLEAU_USER TEXT,
                DASHBOARD TEXT,
                PUBLIC_IP_CANDIDATE TEXT
            )
            """
        )

        schema_rows = conn.execute("PRAGMA table_info(freeze_workflow_extended)").fetchall()
        existing_columns = {row[1] for row in schema_rows}
        for column_name, column_type in WORKFLOW_EXTENDED_COLUMNS.items():
            if column_name not in existing_columns:
                conn.execute(
                    f"ALTER TABLE freeze_workflow_extended ADD COLUMN {column_name} {column_type}"
                )

        first_column_name = schema_rows[0][1] if schema_rows else None
        freeze_task_meta = next((row for row in schema_rows if row[1] == "FREEZE_TASK_ID"), None)
        freeze_task_is_required = bool(freeze_task_meta and freeze_task_meta[3] == 1)

        if first_column_name != "FREEZE_TASK_ID" or not freeze_task_is_required:
            self._rebuild_workflow_extended_table(conn)

    def _rebuild_workflow_extended_table(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE freeze_workflow_extended_new (
                FREEZE_TASK_ID TEXT NOT NULL,
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                SESSION_ID TEXT,
                EVENT_ID TEXT,
                EVENT_TYPE TEXT,
                TIMESTAMP_UTC TEXT,
                USER_AGENT TEXT,
                ACCEPT_LANGUAGE TEXT,
                SEC_CH_UA TEXT,
                SEC_CH_UA_PLATFORM TEXT,
                DEVICE_TYPE TEXT,
                TABLEAU_USER TEXT,
                DASHBOARD TEXT,
                PUBLIC_IP_CANDIDATE TEXT
            )
            """
        )

        conn.execute(
            """
            INSERT INTO freeze_workflow_extended_new (
                FREEZE_TASK_ID,
                ID,
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
            )
            SELECT
                COALESCE(
                    NULLIF(TRIM(FREEZE_TASK_ID), ''),
                    'UNBOUND:' || COALESCE(NULLIF(TRIM(EVENT_ID), ''), LOWER(HEX(RANDOMBLOB(8))))
                ),
                ID,
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
            FROM freeze_workflow_extended
            """
        )

        conn.execute("DROP TABLE freeze_workflow_extended")
        conn.execute("ALTER TABLE freeze_workflow_extended_new RENAME TO freeze_workflow_extended")

    def _init_db_2(self):
        warnings.warn(
            "_init_db_2 is deprecated and kept only for legacy compatibility.",
            DeprecationWarning,
            stacklevel=2,
        )
        schema = os.getenv('VERTICA_SCHEMA', 'DM')
        try:
            with self._get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(f"""
                        CREATE TABLE IF NOT EXISTS {schema}.FREEZE_WORKFLOW (
                            TASK_ID VARCHAR(50), REPORT_NAME VARCHAR(255),
                            PERIOD VARCHAR(100), INIT_USER VARCHAR(100),
                            APPROVER_USER VARCHAR(100), STATUS VARCHAR(20) DEFAULT 'PENDING',
                            PARAMS_JSON LONG VARCHAR, COMMENT VARCHAR(500),
                            IS_ACTUAL INTEGER,
                            DATE_CREATE TIMESTAMP, DATE_APPROVE TIMESTAMP
                        )
                    """)
                   
        except Exception as e:
            print(f"Failed to initialize Vertica tables: {e}")

    def check_dependencies(
        self, report_name: str, period_key: str
    ) -> dict[str, Any]:
        """
        Проверяет, все ли предварительные отчёты для данного report_name
        имеют статус APPROVED за period_key.

        Возвращает словарь:
          {
            "has_dependencies": bool,   # есть ли зависимости вообще
            "all_approved":    bool,    # все ли подтверждены
            "required":        list,    # полный список зависимостей
            "approved":        list,    # уже подтверждённые
            "missing":         list,    # ещё не подтверждённые
          }
        """
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

        with sqlite3.connect(self.db_path) as conn:
            for dep in required:
                row = conn.execute(
                    """
                    SELECT TASK_ID FROM FREEZE_WORKFLOW
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
            
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                exists = conn.execute("""
                            SELECT STATUS, APPROVER_USER 
                            FROM FREEZE_WORKFLOW 
                            WHERE PERIOD = ? 
                            AND REPORT_NAME = ?
                            AND INIT_USER = ? 
                            AND APPROVER_USER = ? 
                            AND STATUS IN (?, ?)
                        """, (
                            period_key,
                            report,
                            initiator,
                            approver,
                            WorkflowStatus.PENDING.value,
                            WorkflowStatus.APPROVED.value,
                        )).fetchone()
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
                
                conn.execute("""
                    INSERT INTO FREEZE_WORKFLOW (
                        TASK_ID, REPORT_NAME, PERIOD, INIT_USER, 
                        APPROVER_USER, PARAMS_JSON, COMMENT,
                        SESSION_ID, EVENT_ID, EVENT_TYPE, PUBLIC_IP_CANDIDATE,
                        DATE_CREATE
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    task_id, report, period_key, initiator, 
                    approver, json.dumps(params), 
                    data.get('comment', ''), 
                    session_id,
                    event_id,
                    event_type,
                    public_ip_candidate,
                    datetime.now().isoformat()
                ))
                conn.commit()
                
                return {
                    "status": RequestResultStatus.CREATED,
                    "task_id": task_id,
                    "approver": approver,
                }
        except Exception as e:
            print(f"Error: {e}")
            raise e

    def backfill_request_context(self, task_id: str, context: dict[str, Any]) -> dict[str, Any]:
        session_id = context.get("session_id")
        event_id = context.get("event_id")
        event_type = context.get("event_type")
        public_ip_candidate = _extract_public_ip_candidate(context)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            existing = conn.execute(
                "SELECT TASK_ID, SESSION_ID, EVENT_ID, EVENT_TYPE, PUBLIC_IP_CANDIDATE FROM FREEZE_WORKFLOW WHERE TASK_ID = ?",
                (task_id,),
            ).fetchone()

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

            conn.execute(
                """
                UPDATE FREEZE_WORKFLOW
                SET SESSION_ID = COALESCE(SESSION_ID, ?),
                    EVENT_ID = COALESCE(EVENT_ID, ?),
                    EVENT_TYPE = COALESCE(EVENT_TYPE, ?),
                    PUBLIC_IP_CANDIDATE = COALESCE(PUBLIC_IP_CANDIDATE, ?)
                WHERE TASK_ID = ?
                """,
                (session_id, event_id, event_type, public_ip_candidate, task_id),
            )
            conn.commit()

            return {
                "matched_task": True,
                "updated": conn.total_changes > 0,
                "message": "Контекст сопоставлен по task_id",
            }

    def insert_workflow_extended_event(self, event_payload: dict[str, Any]) -> dict[str, Any]:
        server_context = event_payload.get("server_context") or {}
        client_hints = server_context.get("client_hints") or {}
        freeze_task_id = _resolve_required_freeze_task_id(event_payload)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO freeze_workflow_extended (
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
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    freeze_task_id,
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
            conn.commit()

            return {
                "saved": True,
                "row_id": cursor.lastrowid,
                "table": "freeze_workflow_extended",
            }

    def final_approve(self, task_id: str, current_user: str) -> dict[str, Any]:
        # ── Шаг 1: проверки и обновление статуса (если что-то пойдёт не так — 400) ──
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                task = conn.execute(
                    "SELECT * FROM FREEZE_WORKFLOW WHERE TASK_ID = ?", (task_id,)
                ).fetchone()

                if not task:
                    return {"success": False, "message": "Задача не найдена"}
                if task['APPROVER_USER'] != current_user:
                    return {"success": False, "message": f"Нужен аппрув от {task['APPROVER_USER']}"}
                if task['STATUS'] != WorkflowStatus.PENDING.value:
                    return {"success": False, "message": f"Статус: {task['STATUS']}"}

                report_name = task['REPORT_NAME']
                report_meta = REPORTS_SQL.get(report_name)
                if not report_meta:
                    return {"success": False, "message": f"Отчет '{report_name}' не найден в реестре"}

                final_sql = self._build_vertica_sql(task, report_meta)

                # ВЫЗОВ ВЕРТИКИ
                # self.vertica_client.execute(final_sql)
                print(f"✅ Заморозка выполнена для {report_name}")

                now_iso = datetime.now().isoformat()
                conn.execute(
                    "UPDATE FREEZE_WORKFLOW SET STATUS = ?, DATE_APPROVE = ? WHERE TASK_ID = ?",
                    (WorkflowStatus.APPROVED.value, now_iso, task_id),
                )
                conn.commit()

                # Сохраняем копию task как dict — соединение сейчас закроется
                task_dict = dict(task)

        except Exception as e:
            print(f"КРИТИЧЕСКАЯ ОШИБКА В final_approve: {e}")
            return {"success": False, "message": str(e)}

        # ── Шаг 2: выгрузка данных 5.8 из Tableau (ошибка НЕ ломает аппрув) ──
        summary_result = None
        if task_dict.get('REPORT_NAME') == REPORT_5_8_NAME:
            print(f"[5.8] Начинаем выгрузку данных из Tableau...")
            try:
                summary_result = self._fetch_and_save_summary_report(task_dict, now_iso)
            except Exception as e:
                summary_result = {"saved": False, "reason": str(e)}
            print(f"[5.8] Результат выгрузки: {summary_result}")

        return {"success": True, "summary_saved": summary_result}

    def _build_vertica_sql(self, task: sqlite3.Row, base_sql: dict[str, Any]) -> str:
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
    
    def _fetch_and_save_summary_report(self, task: sqlite3.Row, approve_ts: str) -> dict[str, Any]:
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
            print(f"[5.8] Колонки: {list(df.columns)}")
        except Exception as e:
            return {"saved": False, "reason": f"Ошибка выгрузки из Tableau: {e}"}
 
        return self._save_df_to_summary_table(df, task, d_start, d_end, approve_ts)
 
    def _save_df_to_summary_table(
        self,
        df: "pd.DataFrame",
        task: sqlite3.Row,
        d_start: str,
        d_end: str,
        approve_ts: str,
    ) -> dict[str, Any]:
        """Записывает DataFrame построчно в FROZEN_SUMMARY_REPORT_PROFITABILITY."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Перезапись — удаляем старый снапшот
                conn.execute(
                    "DELETE FROM FROZEN_SUMMARY_REPORT_PROFITABILITY WHERE SNAPSHOT_ID = ?",
                    (task['TASK_ID'],),
                )
                for idx, row in df.iterrows():
                    conn.execute(
                        """
                        INSERT INTO FROZEN_SUMMARY_REPORT_PROFITABILITY (
                            SNAPSHOT_ID, INIT_USER, APPROVER_USER,
                            FREEZING_PERIOD_START, FREEZING_PERIOD_END,
                            DATE_FREEZE, LOAD_DATE,
                            ROW_INDEX, ROW_DATA_JSON
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            task['TASK_ID'],
                            task['INIT_USER'],
                            task['APPROVER_USER'],
                            d_start,
                            d_end,
                            approve_ts[:10],
                            approve_ts,
                            int(idx),
                            row.to_json(force_ascii=False),
                        ),
                    )
                conn.commit()
 
            return {"saved": True, "rows_written": len(df), "snapshot_id": task['TASK_ID']}
        except Exception as e:
            print(f"Ошибка _save_df_to_summary_table: {e}")
            return {"saved": False, "reason": str(e)}
 
    def get_summary_report(self, snapshot_id: str) -> dict[str, Any] | None:
        """Возвращает запись сводного отчёта 5.8 по snapshot_id.
        DATA_JSON разбирается в словарь и добавляется как 'data'.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT * FROM FROZEN_SUMMARY_REPORT_PROFITABILITY
                WHERE SNAPSHOT_ID = ?
                """,
                (snapshot_id,),
            ).fetchone()
            if not row:
                return None
            entry = dict(row)
            try:
                entry['data'] = json.loads(entry['DATA_JSON'])
            except Exception:
                entry['data'] = None
            return entry

    def get_user_tasks(self, username: str) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            res = conn.execute(
                "SELECT * FROM FREEZE_WORKFLOW WHERE APPROVER_USER = ? AND STATUS = ?",
                (username, WorkflowStatus.PENDING.value)
            ).fetchall()
            return [dict(r) for r in res]
    
    def get_approved_tasks(
        self,
        report_filter: str | None = None,
        date_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM FREEZE_WORKFLOW WHERE STATUS = ?"
        params = [WorkflowStatus.APPROVED.value]
        
        if report_filter:
            query += " AND REPORT_NAME LIKE ?"
            params.append(f"%{report_filter}%")
        if date_filter:
            # Предполагаем формат даты в БД ISO (YYYY-MM-DD...)
            query += " AND DATE_APPROVE >= ?"
            params.append(date_filter)
            
        query += " ORDER BY DATE_APPROVE DESC"
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            res = conn.execute(query, params).fetchall()
            return [dict(r) for r in res]

    def void_task(self, task_id: str, admin_user: str, comment: str) -> dict[str, Any]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE FREEZE_WORKFLOW 
                    SET STATUS = ?, 
                        IS_ACTUAL = 0,
                        COMMENT = COALESCE(COMMENT, '') || ?
                    WHERE TASK_ID = ?
                """, (
                    WorkflowStatus.VOIDED.value,
                    f" | [ОТЗЫВ {admin_user}: {comment}]",
                    task_id,
                ))
                conn.commit()
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