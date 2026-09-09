from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI

from app import database
from app.routes.tasks import router as tasks_router
from app.routes.tools import router as tools_router
from app.routes.webhooks import router as webhooks_router

app = FastAPI(title="Zephvion AI Voice Agent Backend")
app.include_router(tools_router)
app.include_router(webhooks_router)
app.include_router(tasks_router)


@app.on_event("startup")
def on_startup():
    database.init_db()


@app.get("/health")
def health():
    return {"status": "ok"}
