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
                            DO_REPORT VARCHAR(250),
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
                    self._ensure_frozen_main_table(cursor, schema)
                    self._ensure_frozen_securities_table(cursor, schema)
                    self._ensure_frozen_profitability_summary_table(cursor, schema)
                    self._ensure_frozen_data_detailed_report_table(cursor, schema)
        except Exception as e:
            print(f"Failed to initialize Vertica DB table: {e}")

    def _ensure_frozen_summary_table(self, cursor, schema) -> None:
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {schema}.FROZEN_SUMMARY_REPORT_PROFITABILITY (
                SNAPSHOT_ID   VARCHAR(50),
                DO_REPORT VARCHAR(255),
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
    
    def _ensure_frozen_data_detailed_report_table(self, cursor, schema: str) -> None:
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {schema}.FROZEN_DATA_DETAILED_REPORT (
                "SNAPSHOT_ID"                                  VARCHAR(100),
                DO_REPORT                                      VARCHAR(255),
                "INIT"                                         VARCHAR(100),
                "APPROVER"                                     VARCHAR(100),
                "FREEZING_PERIOD_START"                        DATE,
                "FREEZING_PERIOD_END"                          DATE,
                "DATE_FREEZE"                                  DATE,
                "LOAD_DATE"                                    TIMESTAMP,
                "AMOUNT_CLOSE"                                 NUMERIC(20,2),
                "AVG_MRKT_RATE"                                NUMERIC(20,6),
                "BALANCE_AMOUNT_FCY"                           NUMERIC(20,2),
                "BALANCE_AMOUNT_LCY"                           NUMERIC(20,2),
                "BANK_ID"                                      BIGINT,
                "BANK_NAME"                                    VARCHAR(600),
                "CLOSING_VALUE"                                NUMERIC(20,2),
                "CONTRACT_NAME"                                VARCHAR(500),
                "CONTRACT_TYPE"                                VARCHAR(256),
                "COUNTERPARTY_RATING_RANGE"                    VARCHAR(255),
                "COUPON_IR_KIND"                               VARCHAR(256),
                "CPN_RATE"                                     NUMERIC(20,6),
                "CURRENCY_CODE"                                VARCHAR(10),
                "DATE_END"                                     DATE,
                "DATE_START"                                   DATE,
                "DM_DATE"                                      DATE,
                "FEE_SUM_FCY"                                  NUMERIC(20,2),
                "FEE_SUM_LCY"                                  NUMERIC(20,2),
                "FIN_SOURCE_NAME"                              VARCHAR(600),
                "GUAR_PROJ_NAME"                               VARCHAR(1000),
                "INC_TOTAL_AMOUNT_INVESTMENT_INCOME"           NUMERIC(20,2),
                "INTEREST_BASE"                                VARCHAR(50),
                "INTEREST_RATE"                                NUMERIC(20,6),
                "LIMIT_DEAL_ID"                                BIGINT,
                "LIMIT_TOOL_CODE"                              BIGINT,
                "LIMIT_TOOL_NAME"                              VARCHAR(1000),
                "MIN_RATING_SCALE"                             VARCHAR(255),
                "NOMINAL_AMOUNT"                               NUMERIC(20,2),
                "NOT_IN_VSDS"                                  BOOLEAN,
                "NOT_REDUCE_MINIMAL_BALANCE_OF_ACCOUNT_NUMBER" NUMERIC(20,2),
                "NUMBER"                                       VARCHAR(600),
                "OPERATION_AMOUNT_LCY (DM_LIMIT_CONTRACT)"     NUMERIC(20,2),
                "ORGANIZATION_ID"                              BIGINT,
                "ORGANIZATION_NAME_LEGAL"                      VARCHAR(1000),
                "ORGANIZATION_NAME_SHORT"                      VARCHAR(400),
                "ORIGINAL_AMOUNT_OF_ACCOUNT_NUMBER"            NUMERIC(20,2),
                "PARENT_ORGANIZATION_NAME_SHORT"               VARCHAR(255),
                "PERIODICITY_PAYMENT_REMUNERATION"             VARCHAR(255),
                "QUANTITY (DM_LIMIT_CONTRACT)"                 NUMERIC(20,2),
                "QUANTITY_REMAINING_BALANCE"                   NUMERIC(20,2),
                "REPORT_DATE"                                  DATE,
                "RESERVE_SUM"                                  NUMERIC(20,2),
                "SECURITY_RATING"                              VARCHAR(100),
                "SECURITY_RATING_SCALE"                        VARCHAR(100),
                "SECURITY_YIELD"                               NUMERIC(20,6),
                "TOTAL_NOMINAL_VALUE"                          NUMERIC(20,2),
                "TOTAL_PROVISION_ON_COUPON"                    NUMERIC(20,2),
                "BANK_RATING"                                  VARCHAR(255),
                "CURRENCY_CODE (DI_EXCHANGE_RATES)"            VARCHAR(10),
                "VALUE_EXCHANGE"                               NUMERIC(20,6),
                "IBAN"                                         VARCHAR(255),
                "ACC_TYPE"                                     VARCHAR(256),
                "H_LOT_OF_SECURITY_BK"                         VARCHAR(255),
                "OPERATION_AMOUNT_FCY_SECURITY"                NUMERIC(20,2),
                "OPERATION_AMOUNT_LCY_SECURITY"                NUMERIC(20,2),
                "OPERATION_TYPE"                               VARCHAR(256),
                "PRICE"                                        NUMERIC(20,6),
                "QUANTITY_SECURITY"                            NUMERIC(20,2),
                "TRANSACTION_ID"                               VARCHAR(100),
                "ACT_DATE"                                     DATE,
                "CURRENCY_CODE_STR"                            VARCHAR(10),
                "ACT_DATE (Custom SQL Query)"                  DATE,
                "LIMIT_DEAL_ID (Custom SQL Query)"             BIGINT,
                "dohod"                                        NUMERIC(20,2),
                "p_ACT_DATE"                                   DATE,
                "p_type"                                       VARCHAR(100),
                "type"                                         VARCHAR(100)
            )
        """)

    def _ensure_frozen_securities_table(self, cursor, schema: str) -> None:
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {schema}.FROZEN_PROFITABILITY_REPORT_SECURITIES (
                "SNAPSHOT_ID"              VARCHAR(50),
                "DO_REPORT"                VARCHAR(255),
                "INIT"                     VARCHAR(100),
                "APPROVER"                 VARCHAR(100),
                "FREEZING_PERIOD_START"    VARCHAR(50),
                "FREEZING_PERIOD_END"      VARCHAR(50),
                "DATE_FREEZE"              DATE,
                "LOAD_DATE"                TIMESTAMP,
                "COUNTERPARTY_NAME_LEGAL"  VARCHAR(500),
                "CPN_RATE"                 FLOAT,
                "CURRENCY_CODE"            VARCHAR(80),
                "DAYS_COUNT"               FLOAT,
                "DM_DATE"                  DATE,
                "END_DATE"                 DATE,
                "END_SUM_FCY"              FLOAT,
                "END_SUM_LCY"              FLOAT,
                "H_LEGAL_ENTITY_ID"        VARCHAR(80),
                "H_ORGANIZATION_ID"        VARCHAR(80),
                "INCOME_FCY"               FLOAT,
                "INCOME_LCY"               FLOAT,
                "INCOME_SUM_FCY"           FLOAT,
                "INCOME_SUM_LCY"           FLOAT,
                "INTEREST_PERIOD"          BIGINT,
                "LIMIT_DEAL_ID"            BIGINT,
                "LOT_ID"                   VARCHAR(255),
                "NUMBER"                   VARCHAR(400),
                "ORGANIZATION_NAME_LEGAL"  VARCHAR(500),
                "ORGANIZATION_NAME_SHORT"  VARCHAR(80),
                "START_DATE"               DATE,
                "START_SUM_FCY"            FLOAT,
                "START_SUM_LCY"            FLOAT
            )
        """)

    def _ensure_frozen_profitability_summary_table(self, cursor, schema: str) -> None:
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {schema}.FROZEN_FULL_REPORT_PROFITABILITY (
                SNAPSHOT_ID                         VARCHAR(50),
                DO_REPORT                VARCHAR(255),
                INIT                                VARCHAR(100),
                APPROVER                            VARCHAR(100),
                FREEZING_PERIOD_START               VARCHAR(50),
                FREEZING_PERIOD_END                 VARCHAR(50),
                DATE_FREEZE                         DATE,
                LOAD_DATE                           TIMESTAMP,
                "AMOUNT_CLOSE"                      FLOAT,
                "BALANCE_AMOUNT_FCY"                FLOAT,
                "BALANCE_AMOUNT_LCY"                FLOAT,
                "BANK_NAME"                         VARCHAR(1000),
                "CURRENCY_CODE"                     VARCHAR(80),
                "DATE_END"                          DATE,
                "DATE_START"                        DATE,
                "DM_DATE"                           DATE,
                "INTEREST_PERIOD"                   INT,
                "INTEREST_RATE"                     FLOAT,
                "LIMIT_DEAL_ID"                     INT,
                "LIMIT_TOOL_CODE"                   INT,
                "LIMIT_TOOL_NAME"                   VARCHAR(80),
                "NOT_INCLUDED_TO_INCOME"            BOOLEAN,
                "ORGANIZATION_NAME_LEGAL"           VARCHAR(1000),
                "ORGANIZATION_NAME_SHORT"           VARCHAR(500),
                "PARENT_ORGANIZATION_NAME_SHORT"    VARCHAR(1000),
                "START_DATE"                        DATE,
                "CURRENCY_CODE (DM_INCOME_SECURITY)" VARCHAR(80),
                "START_SUM_FCY"                     FLOAT,
                "START_SUM_LCY"                     FLOAT,
                "INCOME_FCY"                        FLOAT,
                "INCOME_LCY"                        FLOAT,
                "INCOME_SUM_FCY"                    FLOAT,
                "INCOME_SUM_LCY"                    FLOAT,
                "VALUE (DI_EXCHANGE_RATES_SUKO1)"   FLOAT,
                "VALUE"                             FLOAT
            )
        """)

    def _ensure_frozen_main_currency_table(self, cursor, schema: str) -> None:
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {schema}.FROZEN_PROFITABILITY_REPORT_MAIN_CURRENCY (
                "SNAPSHOT_ID"                   VARCHAR(50),
                "DO_REPORT"                VARCHAR(255),
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
                "ORGANIZATION_NAME_LEGAL"       VARCHAR(1000),
                "ORGANIZATION_NAME_SHORT"       VARCHAR(400),
                "VALUE"                         NUMERIC(20, 6),
                "VALUE (DI_EXCHANGE_RATES_SUKO1)" NUMERIC(20, 6)
            )
        """)

    def _ensure_frozen_main_table(self, cursor, schema: str) -> None:
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {schema}.FROZEN_PROFITABILITY_REPORT_MAIN (
                "SNAPSHOT_ID"                   VARCHAR(50),
                "DO_REPORT"                VARCHAR(255),
                "INIT"                          VARCHAR(100),
                "APPROVER"                      VARCHAR(100),
                "FREEZING_PERIOD_START"         VARCHAR(50),
                "FREEZING_PERIOD_END"           VARCHAR(50),
                "DATE_FREEZE"                   DATE,
                "LOAD_DATE"                     TIMESTAMP,
                "AMOUNT_CLOSE"                  NUMERIC(20, 6),
                "BALANCE_AMOUNT_LCY"            NUMERIC(20, 6),
                "BANK_NAME"                     VARCHAR(600),
                "CURRENCY_CODE"                 VARCHAR(80),
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
