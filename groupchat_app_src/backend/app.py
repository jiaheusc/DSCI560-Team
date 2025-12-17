from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from contextlib import asynccontextmanager
from datetime import timezone
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(ROOT)

from routes import register_routes
from utils.task import generate_daily_summaries

scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    
    scheduler.add_job(
        generate_daily_summaries, 
        CronTrigger(hour=0, minute=5, timezone=timezone.utc),
        id="daily_summary_job",
        replace_existing=True
    )
    
    scheduler.start()
    
    try:
        yield
    finally:
        scheduler.shutdown()

app = FastAPI(title="GroupChat + Therapist System", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

register_routes(app)

from fastapi import BackgroundTasks

@app.post("/test-trigger-summary")
async def test_trigger_summary(background_tasks: BackgroundTasks):
    background_tasks.add_task(generate_daily_summaries)
    return {"ok": True, "message": "任务已在后台启动，请查看控制台日志"}

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/", StaticFiles(directory="../frontend", html=True), name="frontend")