import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

_LOCK = threading.Lock()


def _is_enabled() -> bool:
    return os.getenv("USER_CONTEXT_AUDIT_ENABLED", "1").strip().lower() not in {"0", "false", "no"}


def _audit_path() -> Path:
    raw_path = os.getenv("USER_CONTEXT_AUDIT_PATH", "audit/user_context_events.jsonl")
    return Path(raw_path)


def persist_user_context_event(event_payload: Dict[str, Any]) -> Dict[str, Any]:
    if not _is_enabled():
        return {
            "enabled": False,
            "saved": False,
            "path": str(_audit_path()),
        }

    target_path = _audit_path()
    record = {
        "ingest_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        **event_payload,
    }

    line = json.dumps(record, ensure_ascii=False)

    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with _LOCK:
            with target_path.open("a", encoding="utf-8") as f:
                f.write(line)
                f.write("\n")
        return {
            "enabled": True,
            "saved": True,
            "path": str(target_path),
        }
    except Exception as e:
        return {
            "enabled": True,
            "saved": False,
            "path": str(target_path),
            "error": str(e),
        }
