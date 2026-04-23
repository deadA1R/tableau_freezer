import os
from app.freezer.db_sqlite import SQLiteBackend
from app.freezer.db_vertica import VerticaBackend


class FreezerSchemaMixin:
    def _get_db_backend(self) -> str:
        backend = (os.getenv("FREEZER_DB_BACKEND") or "").strip().lower()
        if backend in {"sqlite", "vertica"}:
            return backend

        if backend:
            print(f"[db] Unknown FREEZER_DB_BACKEND={backend!r}, fallback to auto mode")

        if getattr(self, "db_path", None):
            return "sqlite"
        return "vertica"

    def _is_sqlite_backend(self) -> bool:
        return self._get_db_backend() == "sqlite"

    def _get_db_connection(self):
        schema = os.getenv("VERTICA_SCHEMA", "DM")
        if self._is_sqlite_backend():
            db_path = getattr(self, "db_path", None) or os.getenv("FREEZER_SQLITE_PATH", "workflow_freeze.db")
            return SQLiteBackend(schema=schema, db_path=db_path).connect()

        return VerticaBackend().connect()

    def _init_db(self):
        schema = os.getenv("VERTICA_SCHEMA", "DM")
        try:
            with self._get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        f"""
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
                    """
                    )
                    self._ensure_workflow_extended_table(cursor, schema)
                    self._ensure_frozen_summary_table(cursor, schema)
                    self._ensure_frozen_main_currency_table(cursor, schema)
                    self._ensure_frozen_securities_table(cursor, schema)
                    self._ensure_frozen_profitability_summary_table(cursor, schema)
        except Exception as e:
            print(f"Failed to initialize Vertica DB table: {e}")

    def _ensure_frozen_summary_table(self, cursor, schema) -> None:
        """Создает таблицу для заморозки сводной формы 5.8."""
        cursor.execute(
            f"""
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
        cursor.execute(
            f"""
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
        """
        )

    def _ensure_frozen_profitability_summary_table(self, cursor, schema: str) -> None:
        cursor.execute(
            f"""
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
        """
        )

    def _ensure_frozen_main_currency_table(self, cursor, schema: str) -> None:
        cursor.execute(
            f"""
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
        """
        )

    def _ensure_frozen_main_table(self, cursor, schema: str) -> None:
        cursor.execute(
            f"""
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
        """
        )

    def _ensure_workflow_extended_table(self, cursor, schema: str) -> None:
        cursor.execute(
            f"""
        CREATE TABLE IF NOT EXISTS {schema}.FREEZE_WORKFLOW_EXTENDED (
            FREEZE_TASK_ID VARCHAR(50) NOT NULL,
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
    """
        )
