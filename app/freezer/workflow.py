# -*- coding: utf-8 -*-
import json
import os
import uuid
from datetime import datetime as dt
from typing import Any, TYPE_CHECKING

from app.config import REPORT_5_8_NAME, REPORT_5_8_WORKBOOK, REPORT_5_8_WORKSHEET
from app.report_registry import REPORT_DEPENDENCIES, REPORTS_SQL
from app.organizations_registry import get_organization_for_user
from app.statuses import RequestResultStatus, WorkflowStatus
from app.freezer.helpers import (
    _extract_public_ip_candidate,
    _get_frozen_table,
    _resolve_period_dates,
    _resolve_required_freeze_task_id,
)

if TYPE_CHECKING:
    import pandas as pd


class FreezerWorkflowMixin:
    def check_dependencies(self, report_name: str, period_key: str, do_report: str) -> dict[str, Any]:
        schema = os.getenv("VERTICA_SCHEMA", "DM")
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
                        f"""
                        SELECT TASK_ID FROM {schema}.FREEZE_WORKFLOW
                        WHERE REPORT_NAME = %s
                        AND PERIOD = %s
                        AND STATUS = %s
                        AND DO_REPORT = %s
                        LIMIT 1
                        """,
                        (dep, period_key, WorkflowStatus.APPROVED.value, do_report),
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

    def check_duplicate(self, report_name: str, period_key: str, do_report: str) -> dict[str, Any]:
      schema = os.getenv("VERTICA_SCHEMA", "DM")
      
      with self._get_db_connection() as conn:
          with conn.cursor("dict") as cursor:
              cursor.execute(
                  f"""
                  SELECT TASK_ID, STATUS, INIT_USER, APPROVER_USER 
                  FROM {schema}.FREEZE_WORKFLOW
                  WHERE REPORT_NAME = %s
                  AND PERIOD = %s
                  AND DO_REPORT = %s
                  AND STATUS IN (%s, %s)
                  LIMIT 1
                  """,
                  (
                      report_name, 
                      period_key, 
                      do_report,
                      WorkflowStatus.PENDING.value, 
                      WorkflowStatus.APPROVED.value,
                  ),
              )
              existing = cursor.fetchone()
              
              if existing:
                  return {
                      "is_duplicate": True,
                      "status": existing["STATUS"],
                      "init_user": existing["INIT_USER"],
                      "approver_user": existing["APPROVER_USER"],
                  }
              return {"is_duplicate": False}
    
    
    def create_request(self, data: dict[str, Any]) -> dict[str, Any]:
        schema = os.getenv("VERTICA_SCHEMA", "DM")
        try:
            report = data.get("dashboard", "Unknown")
            params = data.get("params", {})
            session_id = data.get("session_id")
            event_id = data.get("event_id")
            event_type = data.get("event_type")
            public_ip_candidate = _extract_public_ip_candidate(data)

            d_s, d_e = _resolve_period_dates(report, params)
            period_key = f"{d_s}_{d_e}"
            approver = data.get("approver", "tabladmin")
            initiator = data.get("user", "unknown")
            do_report = get_organization_for_user(initiator)

            dep_check = self.check_dependencies(report, period_key, do_report)
            if dep_check["has_dependencies"] and not dep_check["all_approved"]:
                return {
                    "success": False,
                    "status": "DEPENDENCIES_NOT_MET",
                    "message": (
                        f"Невозможно создать задачу: не все обязательные отчеты "
                        f"подтверждены за период {period_key}."
                    ),
                    "dependencies": dep_check,
                }

            with self._get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        f"SELECT STATUS, APPROVER_USER FROM {schema}.FREEZE_WORKFLOW WHERE PERIOD = %s AND REPORT_NAME = %s AND INIT_USER = %s AND APPROVER_USER = %s AND STATUS IN (%s, %s) AND DO_REPORT = %s",
                        (
                            period_key,
                            report,
                            initiator,
                            approver,
                            WorkflowStatus.PENDING.value,
                            WorkflowStatus.APPROVED.value,
                            do_report,
                        ),
                    )
                    exists = cursor.fetchone()

                    if exists:
                        status_msg = (
                            "уже подтвержден"
                            if exists["STATUS"] == WorkflowStatus.APPROVED.value
                            else f"ожидает аппрува от {exists['APPROVER_USER']}"
                        )
                        return {
                            "status": RequestResultStatus.EXISTS,
                            "message": f"Срез за период {period_key} {status_msg}. Чтобы создать новый, старый должен быть аннулирован (VOIDED).",
                        }

                    task_id = str(uuid.uuid4())[:8]

                    if initiator == approver:
                        if initiator != "tabladmin":
                            return {
                                "success": False,
                                "message": "Ошибка безопасности: Инициатор и Аппрувер не могут совпадать.",
                            }

                    cursor.execute(
                        f"""
                        INSERT INTO {schema}.FREEZE_WORKFLOW (
                            TASK_ID, REPORT_NAME, PERIOD, DO_REPORT, INIT_USER,
                            APPROVER_USER, PARAMS_JSON, COMMENT, IS_ACTUAL, SESSION_ID, EVENT_ID, EVENT_TYPE, PUBLIC_IP_CANDIDATE, DATE_CREATE
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                        (
                            task_id,
                            report,
                            period_key,
                            do_report,
                            initiator,
                            approver,
                            json.dumps(params),
                            data.get("comment", ""),
                            "1",
                            session_id,
                            event_id,
                            event_type,
                            public_ip_candidate,
                            dt.now().isoformat(),
                        ),
                    )

            return {
                "status": RequestResultStatus.CREATED,
                "task_id": task_id,
                "approver": approver,
            }
        except Exception as e:
            print(f"Error: {e}")
            raise e

    def backfill_request_context(self, task_id: str, context: dict[str, Any]) -> dict[str, Any]:
        schema = os.getenv("VERTICA_SCHEMA", "DM")
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

                    if existing[1] and session_id and existing[1] != session_id:
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
        schema = os.getenv("VERTICA_SCHEMA", "DM")
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
                            _resolve_required_freeze_task_id(event_payload),
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
                        "table": f"{schema}.FREEZE_WORKFLOW_EXTENDED",
                    }
        except Exception as e:
            print(f"Error in insert_workflow_extended_event: {e}")
            raise e

    def final_approve(self, task_id: str, current_user: str) -> dict[str, Any]:
        schema = os.getenv("VERTICA_SCHEMA", "DM")
        try:
            with self._get_db_connection() as conn:
                with conn.cursor("dict") as cursor:
                    cursor.execute(f"SELECT * FROM {schema}.FREEZE_WORKFLOW WHERE TASK_ID = %s", (task_id,))
                    task = cursor.fetchone()

                    if not task:
                        return {"success": False, "message": "Задача не найдена"}
                    if task["APPROVER_USER"] != current_user:
                        return {"success": False, "message": f"Нужен аппрув от {task['APPROVER_USER']}"}
                    if task["STATUS"] != WorkflowStatus.PENDING.value:
                        return {"success": False, "message": f"Статус: {task['STATUS']}"}

                    db_name = task["REPORT_NAME"]

                    report_meta = REPORTS_SQL.get(db_name)
                    if not report_meta:
                        return {"success": False, "message": f"Отчет '{db_name}' не найден в реестре"}

                    final_sql = self._build_vertica_sql(task, report_meta)

                    target_table = _get_frozen_table(db_name)
                    print(f"[freeze] Отчет: {db_name!r} -> таблица: {schema}.{target_table}")

                    if self._is_sqlite_backend():
                        print("[freeze] SQLite backend detected: пропускаем INSERT ... SELECT для snapshot-данных")
                    else:
                        cursor.execute(
                            f"""
                            INSERT INTO {schema}.{target_table}
                            {final_sql}
                        """
                        )
                        print(f"? Заморозка выполнена для {db_name}")

                    cursor.execute(
                        f"UPDATE {schema}.FREEZE_WORKFLOW SET STATUS = %s, DATE_APPROVE = %s WHERE TASK_ID = %s",
                        (WorkflowStatus.APPROVED.value, dt.now(), task_id),
                    )

                    task_dict = dict(task)

        except Exception as e:
            print(f"КРИТИЧЕСКАЯ ОШИБКА В final_approve: {e}")
            return {"success": False, "message": str(e)}

        summary_result = None
        if task_dict.get("REPORT_NAME") == REPORT_5_8_NAME:
            print("[5.8] Начинаем выгрузку данных из Tableau...")
            try:
                summary_result = self._fetch_and_save_summary_report(task_dict, dt.now())
            except Exception as e:
                summary_result = {"saved": False, "reason": str(e)}
            print(f"[5.8] Результат выгрузки: {summary_result}")

        return {"success": True, "summary_saved": summary_result}

    def _approve_tasks(self, task_ids: list[str], current_user: str) -> dict[str, Any]:
        """Batch approval of multiple tasks by a single approver."""
        unique_task_ids = [task_id for task_id in dict.fromkeys(task_ids) if task_id]
        if not unique_task_ids:
            return {"success": False, "message": "Список задач пуст"}

        schema = os.getenv("VERTICA_SCHEMA", "DM")
        try:
            with self._get_db_connection() as conn:
                with conn.cursor("dict") as cursor:
                    # Pre-check all tasks
                    tasks_to_approve = []
                    for task_id in unique_task_ids:
                        cursor.execute(f"SELECT * FROM {schema}.FREEZE_WORKFLOW WHERE TASK_ID = %s", (task_id,))
                        task = cursor.fetchone()

                        if not task:
                            return {"success": False, "message": f"Задача {task_id} не найдена"}
                        if task["APPROVER_USER"] != current_user:
                            return {"success": False, "message": f"Нужен аппрув от {task['APPROVER_USER']}"}
                        if task["STATUS"] != WorkflowStatus.PENDING.value:
                            return {"success": False, "message": f"Статус: {task['STATUS']}"}

                        db_name = task["REPORT_NAME"]
                        report_meta = REPORTS_SQL.get(db_name)
                        if not report_meta:
                            return {"success": False, "message": f"Отчет '{db_name}' не найден в реестре"}

                        tasks_to_approve.append((task, report_meta))

                    # Process all tasks
                    now = dt.now()
                    summary_jobs = []

                    for task, report_meta in tasks_to_approve:
                        db_name = task["REPORT_NAME"]
                        final_sql = self._build_vertica_sql(task, report_meta)
                        target_table = _get_frozen_table(db_name)
                        print(f"[freeze] Отчет: {db_name!r} -> таблица: {schema}.{target_table}")

                        if not self._is_sqlite_backend():
                            cursor.execute(
                                f"""
                                INSERT INTO {schema}.{target_table}
                                {final_sql}
                            """
                            )
                            print(f"✅ Заморозка выполнена для {db_name}")

                        cursor.execute(
                            f"UPDATE {schema}.FREEZE_WORKFLOW SET STATUS = %s, DATE_APPROVE = %s WHERE TASK_ID = %s",
                            (WorkflowStatus.APPROVED.value, now, task["TASK_ID"]),
                        )

                        summary_jobs.append(dict(task))

        except Exception as e:
            print(f"КРИТИЧЕСКАЯ ОШИБКА В _approve_tasks: {e}")
            return {"success": False, "message": str(e)}

        # Post-process for 5.8 reports
        summary_results = []
        for task_dict in summary_jobs:
            if task_dict.get("REPORT_NAME") == REPORT_5_8_NAME:
                print("[5.8] Начинаем выгрузку данных из Tableau...")
                try:
                    summary_result = self._fetch_and_save_summary_report(task_dict, now)
                except Exception as e:
                    summary_result = {"saved": False, "reason": str(e)}
                print(f"[5.8] Результат выгрузки: {summary_result}")
                summary_results.append({"task_id": task_dict.get("TASK_ID"), "result": summary_result})

        return {
            "success": True,
            "approved_task_ids": unique_task_ids,
            "summary_saved": summary_results,
        }

    def _build_vertica_sql(self, task, base_sql: dict[str, Any]) -> str:
        params = json.loads(task["PARAMS_JSON"])
        sql_template = base_sql.get("template")
        tool_code = base_sql.get("tool_code")
        d_start_raw = params.get("Дата начала периода", "01.01.2025")
        d_end_raw = params.get("Дата окончания периода", "30.01.2025")
        currency_filter = base_sql.get("currency_filter", "")

        try:
            date_start = dt.strptime(d_start_raw, "%d.%m.%Y").strftime("%Y-%m-%d")
            date_end = dt.strptime(d_end_raw, "%d.%m.%Y").strftime("%Y-%m-%d")
        except ValueError:
            date_start = d_start_raw
            date_end = d_end_raw

        snapshot_id = task["TASK_ID"]
        init_user = task["INIT_USER"]
        approver_user = task["APPROVER_USER"]
        do_report = task["DO_REPORT"]
        report_name = task["REPORT_NAME"]

        is_securities_report = report_name in {
            "Слайд 5.5. Отчет по доходности ЦБ в тенге",
            "Слайд 5.6. Отчет по доходности ЦБ в валюте",
        }
        
        if is_securities_report and do_report == "АКК":
            do_report_filter = "'АКК','КАФ'"
        elif is_securities_report and do_report == "БРК":
            do_report_filter = "'БРК','ФРП'"
        else:
            do_report_filter = f"'{do_report}'"

        final_query = (
            sql_template.replace("{ToolCode}", str(tool_code))
            .replace("{DateStart}", date_start)
            .replace("{DateEnd}", date_end)
            .replace("{SnapshotID}", snapshot_id)
            .replace("{InitUser}", init_user)
            .replace("{ApproverUser}", approver_user)
            .replace("{CurrencyFilter}", currency_filter)
            .replace("{DoReport}", do_report)
            .replace("{DoReportFilter}", do_report_filter)
        )

        return final_query

    def _fetch_and_save_summary_report(self, task: dict[str, Any], approve_ts: str) -> dict[str, Any]:
        if self._tableau_server is None:
            return {"saved": False, "reason": "Tableau Server credentials not configured in .env"}

        params = json.loads(task["PARAMS_JSON"])
        d_start, d_end = _resolve_period_dates(task["REPORT_NAME"], params)

        tableau_params = {
            "Дата начала периода": d_start,
            "Дата окончания периода": d_end,
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
        schema = os.getenv("VERTICA_SCHEMA", "DM")
        try:
            with self._get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        f"DELETE FROM {schema}.FROZEN_SUMMARY_REPORT_PROFITABILITY WHERE SNAPSHOT_ID = %s",
                        (task["TASK_ID"],),
                    )

                    rows_to_insert = [
                        (
                            task["TASK_ID"],
                            task["DO_REPORT"],
                            task["INIT_USER"],
                            task["APPROVER_USER"],
                            d_start,
                            d_end,
                            str(approve_ts)[:10],
                            str(approve_ts),
                            str(row.iloc[0]),
                            str(row.iloc[1]),
                        )
                        for _, row in df.iterrows()
                    ]

                    cursor.executemany(
                        f"""
                        INSERT INTO {schema}.FROZEN_SUMMARY_REPORT_PROFITABILITY (
                            SNAPSHOT_ID, DO_REPORT, INIT_USER, APPROVER_USER,
                            FREEZING_PERIOD_START, FREEZING_PERIOD_END,
                            DATE_FREEZE, LOAD_DATE,
                            NAME_INDICATOR, VALUE_INDICATOR
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        rows_to_insert,
                    )

            return {"saved": True, "rows_written": len(df), "snapshot_id": task["TASK_ID"]}
        except Exception as e:
            print(f"Ошибка _save_df_to_summary_table: {e}")
            return {"saved": False, "reason": str(e)}

    def get_user_tasks(self, username: str) -> list[dict[str, Any]]:
        schema = os.getenv("VERTICA_SCHEMA", "DM")
        with self._get_db_connection() as conn:
            with conn.cursor("dict") as cursor:
                cursor.execute(
                    f"SELECT * FROM {schema}.FREEZE_WORKFLOW WHERE APPROVER_USER = %s AND STATUS = %s",
                    (username, WorkflowStatus.PENDING.value),
                )
                res = cursor.fetchall()

                for r in res:
                    if r.get("DATE_CREATE"):
                        r["DATE_CREATE"] = str(r["DATE_CREATE"])
                    if r.get("DATE_APPROVE"):
                        r["DATE_APPROVE"] = str(r["DATE_APPROVE"])
                return res

    def get_approved_tasks(
        self,
        report_filter: str | None = None,
        date_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        schema = os.getenv("VERTICA_SCHEMA", "DM")
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
            with conn.cursor("dict") as cursor:
                cursor.execute(query, params)
                res = cursor.fetchall()

                for r in res:
                    if r.get("DATE_CREATE"):
                        r["DATE_CREATE"] = str(r["DATE_CREATE"])
                    if r.get("DATE_APPROVE"):
                        r["DATE_APPROVE"] = str(r["DATE_APPROVE"])
                return res

    def void_task(self, task_id: str, admin_user: str, comment: str) -> dict[str, Any]:
        schema = os.getenv("VERTICA_SCHEMA", "DM")
        try:
            with self._get_db_connection() as conn:
                with conn.cursor("dict") as cursor:
                    query = f"""
                        UPDATE {schema}.FREEZE_WORKFLOW
                        SET STATUS = %s,
                            IS_ACTUAL = 0,
                            COMMENT = COALESCE(COMMENT, '') || %s,
                            DATE_VOIDED = %s
                        WHERE TASK_ID = %s
                    """

                    cursor.execute(
                        query,
                        (WorkflowStatus.VOIDED.value, f" | [ОТЗЫВ {admin_user}: {comment}]", dt.now(), task_id),
                    )
                return {"success": True}
        except Exception as e:
            return {"success": False, "message": str(e)}
