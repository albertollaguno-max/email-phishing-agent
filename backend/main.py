from fastapi import FastAPI, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from database import init_db
from auth import get_current_user, get_current_user_no_role, UserUser
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

# Allow React frontend to access the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For production, restrict this to frontend URL
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
    # Start the IMAP scanning worker in background
    app.state.scheduler = start_background_tasks()

@app.get("/health")
def health_check():
    return {"status": "ok", "message": "Email Phishing Agent API is running"}

@app.get("/api/auth/me")
async def get_me(current_user: UserUser = Depends(get_current_user_no_role)):
    """Return current user info with roles (decoded server-side from JWT)."""
    return current_user
@app.post("/api/check-emails")
async def check_emails_now(
    background_tasks: BackgroundTasks,
    current_user: UserUser = Depends(get_current_user)
):
    """Manually trigger an email check cycle immediately."""
    background_tasks.add_task(run_agent_loop)
    return {"status": "ok", "message": "Email check started in background"}

