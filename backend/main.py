from fastapi import FastAPI, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from database import init_db
from auth import get_current_user, UserUser
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Email Phishing Agent API",
    description="Backend API for the Email Phishing Agent Dashboard",
    version="1.0.0"
)

from routers import senders, logs
from agent_loop import start_background_tasks, run_agent_loop

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(senders.router, prefix="/api")
app.include_router(logs.router, prefix="/api")

@app.on_event("startup")
async def startup_event():
    logger.info("Starting up API and initializing database...")
    init_db()
    app.state.scheduler = start_background_tasks()

@app.get("/health")
def health_check():
    return {"status": "ok", "message": "Email Phishing Agent API is running"}

@app.post("/api/check-emails")
async def check_emails_now(
    background_tasks: BackgroundTasks,
    current_user: UserUser = Depends(get_current_user)
):
    """Manually trigger an email check cycle immediately."""
    background_tasks.add_task(run_agent_loop)
    return {"status": "ok", "message": "Email check started in background"}
