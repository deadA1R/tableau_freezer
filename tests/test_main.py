import os
import json
import sqlite3
import pytest
from fastapi.testclient import TestClient

from main import app, freezer
from app.statuses import RequestResultStatus

# Подсунем тестовую SQLite-базу, чтобы не засорять боевую "workflow_freeze.db"
TEST_DB_PATH = "test_workflow_freeze.db"

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    # 1. Подменяем путь к БД для глобального экземпляра freezer, который объявлен в main.py
    freezer.db_path = TEST_DB_PATH
    # 2. Инициализируем тестовые таблицы
    freezer._init_db()
    
    yield  # Здесь запускаются все тесты
    
    # 3. После окончания тестов удаляем тестовую БД
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

client = TestClient(app)

# Фикстура для сохранения созданного task_id между тестами
class TestState:
    task_id = None

state = TestState()


def test_check_admin_true():
    # Тест проверки прав админа (предусмотрен в config.py: tabladmin)
    response = client.get("/check-admin?user=tabladmin")
    assert response.status_code == 200
    assert response.json() == {"is_admin": True}

def test_check_admin_false():
    # Тест юзера не из конфига
    response = client.get("/check-admin?user=randomuser")
    assert response.status_code == 200
    assert response.json() == {"is_admin": False}

def test_request_freeze_unknown_report():
    # Попытка запроса с неизвестным отчетом
    response = client.post("/request-freeze", json={
        "dashboard": "Какой-то левый отчет",
        "user": "test_init",
        "approver": "tabladmin"
    })
    assert response.status_code == 400
    assert "не описан в реестре" in response.json()["detail"]

def test_request_freeze_success():
    # Создание успешной задачи
    payload = {
        "dashboard": "Слайд 1. Отчет по операциям репо (1.1)",
        "user": "test_initiator",
        "approver": "tabladmin",
        "params": {
            "Дата начала периода": "01.01.2025",
            "Дата окончания периода": "31.01.2025"
        },
        "comment": "Pytest Auto-test",
        "session_id": "sess-req-1",
        "event_id": "evt-req-1",
        "event_type": "freeze_request",
        "public_ip_candidate": "77.240.44.25",
    }
    response = client.post("/request-freeze", json=payload)
    data = response.json()
    
    assert response.status_code == 200
    assert data["status"] == RequestResultStatus.CREATED.value
    assert "task_id" in data
    assert data["approver"] == "tabladmin"
    
    state.task_id = data["task_id"]


def test_request_freeze_context_fields_persisted_in_db():
    assert state.task_id is not None, "task_id не инициализирован"

    with sqlite3.connect(TEST_DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT SESSION_ID, EVENT_ID, EVENT_TYPE, PUBLIC_IP_CANDIDATE
            FROM FREEZE_WORKFLOW
            WHERE TASK_ID = ?
            """,
            (state.task_id,),
        ).fetchone()

    assert row is not None
    assert row["SESSION_ID"] == "sess-req-1"
    assert row["EVENT_ID"] == "evt-req-1"
    assert row["EVENT_TYPE"] == "freeze_request"
    assert row["PUBLIC_IP_CANDIDATE"] == "77.240.44.25"


def test_audit_user_context_backfills_workflow_context_by_task_id():
    create_response = client.post(
        "/request-freeze",
        json={
            "dashboard": "Слайд 1. Отчет по операциям репо (1.1)",
            "user": "backfill_user",
            "approver": "tabladmin",
            "params": {
                "Дата начала периода": "01.02.2025",
                "Дата окончания периода": "28.02.2025",
            },
            "comment": "Backfill check",
        },
    )
    assert create_response.status_code == 200
    task_id = create_response.json()["task_id"]

    audit_response = client.post(
        "/audit/user-context",
        headers={
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/146.0.0.0 Safari/537.36",
            "x-real-ip": "198.51.100.42",
        },
        json={
            "user": "backfill_user",
            "dashboard": "Слайд 1. Отчет по операциям репо (1.1)",
            "session_id": "sess-backfill-1",
            "event_id": "evt-backfill-1",
            "freeze_task_id": task_id,
            "event_type": "freeze_init_submit",
            "client_context": {
                "public_ip_candidate": "95.47.12.33",
            },
        },
    )

    assert audit_response.status_code == 200
    audit_body = audit_response.json()
    assert audit_body["workflow_context_sync"]["matched_task"] is True

    with sqlite3.connect(TEST_DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT SESSION_ID, EVENT_ID, EVENT_TYPE, PUBLIC_IP_CANDIDATE
            FROM FREEZE_WORKFLOW
            WHERE TASK_ID = ?
            """,
            (task_id,),
        ).fetchone()

    assert row is not None
    assert row["SESSION_ID"] == "sess-backfill-1"
    assert row["EVENT_ID"] == "evt-backfill-1"
    assert row["EVENT_TYPE"] == "freeze_init_submit"
    assert row["PUBLIC_IP_CANDIDATE"] == "95.47.12.33"

def test_request_freeze_duplicate():
    # Попытка создать дубликат, если старый еще PENDING/APPROVED
    payload = {
        "dashboard": "Слайд 1. Отчет по операциям репо (1.1)",
        "user": "test_initiator",
        "approver": "tabladmin",
        "params": {
            "Дата начала периода": "01.01.2025",
            "Дата окончания периода": "31.01.2025"
        }
    }
    response = client.post("/request-freeze", json=payload)
    data = response.json()
    
    assert response.status_code == 200
    assert data["status"] == RequestResultStatus.EXISTS.value
    assert "уже подтвержден" in data["message"] or "ожидает аппрува" in data["message"]

def test_pending_tasks_has_task():
    # Проверяем, что задача упала в список "Ожидающих"
    assert state.task_id is not None, "Задача не была создана в предыдущем тесте"
    
    response = client.get("/pending-tasks?user=tabladmin")
    assert response.status_code == 200
    
    tasks = response.json()
    assert len(tasks) > 0
    # Ищем наш созданный ID в массиве задач
    assert any(t["TASK_ID"] == state.task_id for t in tasks)

def test_approve_task_wrong_user():
    # Попытка аппрува чужим юзером
    response = client.post(f"/approve-task/{state.task_id}?user=wronguser")
    assert response.status_code == 400
    assert "Нужен аппрув от tabladmin" in response.json()["detail"]

def test_approve_task_success():
    # Успешный аппрув правильным юзером
    response = client.post(f"/approve-task/{state.task_id}?user=tabladmin")
    data = response.json()
    
    assert response.status_code == 200
    assert data["status"] == "success"

def test_approved_tasks_has_task():
    # Проверка, что после аппрува задача перешла в архив
    response = client.get("/approved-tasks")
    assert response.status_code == 200
    
    tasks = response.json()
    assert len(tasks) > 0
    assert any(t["TASK_ID"] == state.task_id for t in tasks)

def test_approve_already_approved_task():
    # Попытка снова зааппрувить ту же самую задачу (Статус уже не PENDING)
    response = client.post(f"/approve-task/{state.task_id}?user=tabladmin")
    assert response.status_code == 400
    assert "Статус:" in response.json()["detail"]

def test_void_task_success():
    # Отмена (Аннулирование) задачи
    response = client.post(f"/void-task/{state.task_id}", json={
        "user": "drp_exp",
        "comment": "откат pytest"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True

def test_approved_tasks_no_longer_has_task_or_is_voided():
    # После void_task в APPROVED может не быть этой задачи (если фильтр строго по 'APPROVED')
    response = client.get("/approved-tasks")
    assert response.status_code == 200
    
    tasks = response.json()
    # Так как мы ищем строго STATUS = 'APPROVED' в get_approved_tasks(),
    # аннулированная (VOIDED) задача здесь больше не должна выводиться.
    assert not any(t["TASK_ID"] == state.task_id for t in tasks)


def test_debug_user_context_collects_server_and_client_data():
    response = client.post(
        "/debug/user-context",
        headers={
            "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
            "x-forwarded-for": "203.0.113.10, 10.0.0.1",
            "accept-language": "ru-RU,ru;q=0.9",
            "sec-ch-ua-platform": "\"Linux\"",
        },
        json={
            "user": "debug_user",
            "dashboard": "debug_dashboard",
            "session_id": "session-1",
            "event_id": "event-1",
            "event_type": "manual_debug_probe",
            "client_context": {
                "platform": "Linux x86_64",
                "timezone": "Asia/Almaty",
            },
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert data["user"] == "debug_user"
    assert data["dashboard"] == "debug_dashboard"
    assert data["session_id"] == "session-1"
    assert data["event_id"] == "event-1"
    assert data["event_type"] == "manual_debug_probe"
    assert data["client_context"]["platform"] == "Linux x86_64"
    assert data["client_context"]["timezone"] == "Asia/Almaty"

    server_context = data["server_context"]
    assert server_context["client_ip"] == "203.0.113.10"
    assert server_context["client_ip_source"] == "x-forwarded-for:first"
    assert server_context["browser_name"] == "Chrome"
    assert server_context["browser_major"] == "125"
    assert server_context["os_name"] == "Linux"
    assert server_context["ip_details"]["network_guess"]["network_cidr"] == "203.0.113.0/24"
    assert server_context["network_ip"] == "203.0.113.0"
    assert server_context["client_hints"]["sec_ch_ua_platform"] == "\"Linux\""
    assert server_context["confidence"]["ip_confidence"] == "medium"


def test_audit_user_context_persists_jsonl(tmp_path, monkeypatch):
    audit_file = tmp_path / "user_context_events.jsonl"
    monkeypatch.setenv("USER_CONTEXT_AUDIT_ENABLED", "1")
    monkeypatch.setenv("USER_CONTEXT_AUDIT_PATH", str(audit_file))

    response = client.post(
        "/audit/user-context",
        headers={
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/146.0.0.0 Safari/537.36",
            "x-real-ip": "198.51.100.42",
        },
        json={
            "user": "prod_like_user",
            "dashboard": "prod_dashboard",
            "session_id": "sess-prod-1",
            "event_id": "evt-prod-1",
            "freeze_task_id": "frz-12345",
            "event_type": "session_start",
            "client_context": {
                "timezone": "Asia/Almaty",
                "public_ip_candidate": "77.240.44.25",
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["audit"]["enabled"] is True
    assert body["audit"]["saved"] is True
    assert body["audit"]["path"] == str(audit_file)

    assert audit_file.exists()
    lines = audit_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1

    saved_record = json.loads(lines[0])
    assert saved_record["user"] == "prod_like_user"
    assert saved_record["dashboard"] == "prod_dashboard"
    assert saved_record["session_id"] == "sess-prod-1"
    assert saved_record["event_id"] == "evt-prod-1"
    assert saved_record["freeze_task_id"] == "frz-12345"
    assert saved_record["event_type"] == "session_start"
    assert saved_record["server_context"]["client_ip"] == "198.51.100.42"
    assert saved_record["client_context"]["public_ip_candidate"] == "77.240.44.25"
    assert "ingest_timestamp_utc" in saved_record


def test_audit_user_context_persists_extended_table_row():
    response = client.post(
        "/audit/user-context",
        headers={
            "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
            "accept-language": "ru-RU,ru;q=0.9",
            "sec-ch-ua": '"Chromium";v="125", "Google Chrome";v="125"',
            "sec-ch-ua-platform": '"Linux"',
            "x-real-ip": "203.0.113.10",
        },
        json={
            "user": "tableau_user_1",
            "dashboard": "audit_dashboard",
            "session_id": "sess-ext-1",
            "event_id": "evt-ext-1",
            "freeze_task_id": "task-ext-1",
            "event_type": "freeze_init_submit",
            "client_context": {
                "public_ip_candidate": "77.240.44.25",
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["extended_audit"]["saved"] is True

    with sqlite3.connect(TEST_DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT
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
            FROM freeze_workflow_extended
            WHERE EVENT_ID = ?
            """,
            ("evt-ext-1",),
        ).fetchone()

    assert row is not None
    assert row["FREEZE_TASK_ID"] == "task-ext-1"
    assert row["SESSION_ID"] == "sess-ext-1"
    assert row["EVENT_ID"] == "evt-ext-1"
    assert row["EVENT_TYPE"] == "freeze_init_submit"
    assert row["TIMESTAMP_UTC"] is not None
    assert "Chrome/125.0.0.0" in row["USER_AGENT"]
    assert row["ACCEPT_LANGUAGE"] == "ru-RU,ru;q=0.9"
    assert row["SEC_CH_UA"] == '"Chromium";v="125", "Google Chrome";v="125"'
    assert row["SEC_CH_UA_PLATFORM"] == '"Linux"'
    assert row["DEVICE_TYPE"] == "desktop"
    assert row["TABLEAU_USER"] == "tableau_user_1"
    assert row["DASHBOARD"] == "audit_dashboard"
    assert row["PUBLIC_IP_CANDIDATE"] == "77.240.44.25"