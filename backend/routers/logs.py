from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import List
import os, imaplib

from database import SessionLocal, EmailAnalysisLog, SystemLog
from schemas import EmailAnalysisLogResponse, SystemLogResponse
from auth import get_current_user

IMAP_HOST = os.getenv("IMAP_HOST")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
IMAP_USER = os.getenv("IMAP_USER")
IMAP_PASSWORD = os.getenv("IMAP_PASSWORD")

router = APIRouter(
    prefix="/logs",
    tags=["Logs Management"],
    dependencies=[Depends(get_current_user)]
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/emails")
def get_email_logs(page: int = 1, page_size: int = 20, db: Session = Depends(get_db)):
    """Fetch paginated history of analyzed emails with total count."""
    skip = (page - 1) * page_size
    total = db.query(EmailAnalysisLog).count()
    logs = (
        db.query(EmailAnalysisLog)
        .order_by(EmailAnalysisLog.date_received.desc())
        .offset(skip)
        .limit(page_size)
        .all()
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
        "items": [EmailAnalysisLogResponse.from_orm(l) for l in logs]
    }

@router.delete("/emails/{log_id}")
def delete_email_log(log_id: int, db: Session = Depends(get_db)):
    """Delete a log entry from DB and mark the original IMAP message as UNSEEN."""
    log = db.query(EmailAnalysisLog).filter(EmailAnalysisLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Log entry not found")

    imap_uid = log.message_id  # This is the IMAP UID stored during processing

    # Mark message as UNSEEN in IMAP (both INBOX and Spam)
    for folder in ['INBOX', 'Spam']:
        try:
            with imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT) as imap:
                imap.login(IMAP_USER, IMAP_PASSWORD)
                imap.select(folder)
                # Search by UID
                typ, data = imap.uid('search', None, f'UID {imap_uid}')
                if typ == 'OK' and data[0]:
                    imap.uid('store', imap_uid.encode(), '-FLAGS', '\\Seen')
                    break  # Found and unmarked, stop
        except Exception as e:
            pass  # Silently continue if IMAP fails

    db.delete(log)
    db.commit()
    return {"status": "deleted", "id": log_id}

@router.get("/system", response_model=List[SystemLogResponse])
def get_system_logs(limit: int = 100, skip: int = 0, db: Session = Depends(get_db)):
    """Fetch backend internal tracking logs"""
    logs = db.query(SystemLog).order_by(SystemLog.timestamp.desc()).offset(skip).limit(limit).all()
    return logs

@router.get("/stats")
def get_usage_stats(db: Session = Depends(get_db)):
    """Fetch general usage statistics for dashboard"""
    total_emails = db.query(EmailAnalysisLog).count()
    total_phishing = db.query(EmailAnalysisLog).filter(EmailAnalysisLog.is_fraudulent == True).count()
    total_safe = db.query(EmailAnalysisLog).filter(EmailAnalysisLog.is_fraudulent == False).count()
    
    from sqlalchemy import func
    prompt_tokens = db.query(func.sum(EmailAnalysisLog.prompt_tokens)).scalar() or 0
    completion_tokens = db.query(func.sum(EmailAnalysisLog.completion_tokens)).scalar() or 0
    
    return {
        "total_emails_analyzed": total_emails,
        "total_phishing_detected": total_phishing,
        "total_safe_detected": total_safe,
        "ai_usage": {
            "total_prompt_tokens": prompt_tokens,
            "total_completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens
        }
    }


