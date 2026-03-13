import os
from pathlib import Path
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, ConfigDict
import uvicorn

# Локальные модули
from app.tableau_bd_logic import TableauFreezer
from app.report_registry import REPORTS_SQL  # <--- Cправочник SQL

app = FastAPI(title="Tableau Extension Freezer Workflow")

# Настройки CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"] 
)

freezer = TableauFreezer()

static_dir = Path("static")
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

class FreezeRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user: str = "local"
    dashboard: str
    workbook_url: Optional[str] = "local_workbook"
    
    initiator_user: Optional[str] = "unknown"
    approver_user: Optional[str] = "tabladmin"
    period_start: Optional[str] = "N/A"
    period_end: Optional[str] = "N/A"
    
    params: Dict[str, Any] = {}
    comment: Optional[str] = "Без комментария"

# Функция уведомления второго юзера
def trigger_notification(to_user: str, msg: str):
    print(f"✈️ [NOTIF] Пользователю {to_user} отправлено: {msg}")

# --- ЭНДПОИНТЫ ---

@app.get("/extension-manifest")
async def get_manifest():
    manifest_path = Path("freezer.trex")
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="Манифест не найден")
    return FileResponse(manifest_path, media_type="application/xml")

@app.get("/pending-tasks")
async def get_pending_tasks(user: str = Query(...)):
    return freezer.get_user_tasks(user)

@app.post("/request-freeze")
async def request_freeze(request: FreezeRequest):
    try:
        # Проверяем, есть ли такой отчет в справочнике
        if request.dashboard not in REPORTS_SQL:
             raise HTTPException(status_code=400, detail=f"Отчет '{request.dashboard}' не описан в реестре")

        # Передаем в БД логику
        res = freezer.create_request(request.model_dump(by_alias=True))
        
        if res.get("status") == "exists":
            return res

        trigger_notification(res["approver"], f"Нужен аппрув для {request.dashboard}")
        return res
    except Exception as e:
        print(f"❌ Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/approve-task/{task_id}")
async def approve_task(task_id: str, user: str = Query(...)):
    """
    Здесь происходит основной процесс: 
    1. Проверяем права аппрувера.
    2. Вытаскиваем SQL из реестра.
    3. Выполняем INSERT INTO ... SELECT в Vertica.
    """
    result = freezer.final_approve(task_id, user)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "Ошибка подтверждения"))
        
    return {"status": "success", "message": "Данные успешно заморожены в Vertica"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="localhost", port=8000, reload=True)