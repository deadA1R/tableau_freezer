import uuid
from datetime import datetime as dt
from typing import Any

from app.config import FROZEN_TABLE_FALLBACK, REPORT_FROZEN_TABLE_MAP, REPORTS_WITH_REPORT_DATE


def _get_frozen_table(report_name: str) -> str:
    """Возвращает имя таблицы заморозки для переданного отчета."""
    return REPORT_FROZEN_TABLE_MAP.get(report_name, FROZEN_TABLE_FALLBACK)


def _resolve_period_dates(report_name: str, params: dict[str, Any]) -> tuple[str, str]:
    if report_name in REPORTS_WITH_REPORT_DATE:
        report_date_raw = params.get("Дата отчета") or params.get("ReportDate") or "all"
        d_e = report_date_raw

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

    d_s = params.get("DateStart") or params.get("Дата начала периода") or "all"
    d_e = params.get("DateEnd") or params.get("Дата окончания периода") or "all"

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
