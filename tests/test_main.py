import os
import pytest
from fastapi.testclient import TestClient

from main import app, freezer

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
        "comment": "Pytest Auto-test"
    }
    response = client.post("/request-freeze", json=payload)
    data = response.json()
    
    assert response.status_code == 200
    assert data["status"] == "created"
    assert "task_id" in data
    assert data["approver"] == "tabladmin"
    
    state.task_id = data["task_id"]

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
    assert data["status"] == "exists"
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