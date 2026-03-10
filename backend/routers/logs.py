from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional
import os, imaplib

from database import SessionLocal, EmailAnalysisLog, SystemLog
from schemas import EmailAnalysisLogResponse, SystemLogResponse, FeedbackUpdate
from auth import get_current_user
from pydantic import BaseModel

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


def _imap_action_on_uid(uid: str, mode: str):
    """
    Perform IMAP action on a message UID.
    mode='unseen'     -> remove \\Seen flag (so agent re-processes it)
    mode='permanent'  -> add \\Deleted flag + EXPUNGE (permanently removes from mailbox)
    """
    for folder in ['INBOX', 'Spam', 'Elementos enviados']:
        try:
            with imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT) as imap:
                imap.login(IMAP_USER, IMAP_PASSWORD)
                imap.select(folder)
                typ, data = imap.uid('search', None, f'UID {uid}')
                if typ == 'OK' and data[0].strip():
                    if mode == 'permanent':
                        imap.uid('store', uid.encode(), '+FLAGS', '\\Deleted')
                        imap.expunge()
                    else:  # unseen
                        imap.uid('store', uid.encode(), '-FLAGS', '\\Seen')
                    return True
        except Exception:
            pass
    return False


# ── GET /emails  (filtrado + paginado) ──────────────────────────────────────
@router.get("/emails")
def get_email_logs(
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = Query(None, description="Text search in subject or from_address"),
    verdict: Optional[str] = Query(None, description="phishing | clean | pending"),
    feedback: Optional[str] = Query(None, description="correct | incorrect | unrated"),
    forwarded_by: Optional[str] = Query(None, description="Filter by forwarder email"),
    db: Session = Depends(get_db)
):
    """Paginated + filtered email analysis logs."""
    q = db.query(EmailAnalysisLog)

    if search:
        like = f"%{search}%"
        q = q.filter(or_(
            EmailAnalysisLog.subject.ilike(like),
            EmailAnalysisLog.from_address.ilike(like)
        ))

    if verdict == 'phishing':
        q = q.filter(EmailAnalysisLog.is_fraudulent == True)
    elif verdict == 'clean':
        q = q.filter(EmailAnalysisLog.is_fraudulent == False)
    elif verdict == 'pending':
        q = q.filter(EmailAnalysisLog.is_fraudulent == None)

    if feedback == 'correct':
        q = q.filter(EmailAnalysisLog.user_feedback == 'correct')
    elif feedback == 'incorrect':
        q = q.filter(EmailAnalysisLog.user_feedback == 'incorrect')
    elif feedback == 'unrated':
        q = q.filter(EmailAnalysisLog.user_feedback == None)

    if forwarded_by:
        q = q.filter(EmailAnalysisLog.forwarded_by.ilike(f"%{forwarded_by}%"))

    total = q.count()
    skip = (page - 1) * page_size
    logs = q.order_by(EmailAnalysisLog.date_received.desc()).offset(skip).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
        "items": [EmailAnalysisLogResponse.from_orm(l) for l in logs]
    }


# ── DELETE /emails/{id}  (single, mark unseen) ──────────────────────────────
@router.delete("/emails/{log_id}")
def delete_email_log(
    log_id: int,
    mode: str = Query("unseen", description="unseen | permanent"),
    db: Session = Depends(get_db)
):
    """Delete a log from DB. mode=unseen marks IMAP msg as unread; mode=permanent removes it from mailbox."""
    log = db.query(EmailAnalysisLog).filter(EmailAnalysisLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Log entry not found")

    _imap_action_on_uid(log.message_id, mode)
    db.delete(log)
    db.commit()
    return {"status": "deleted", "id": log_id, "mode": mode}


# ── DELETE /emails/bulk  (multi-select) ─────────────────────────────────────
class BulkDeleteRequest(BaseModel):
    ids: List[int]
    mode: str = "unseen"  # unseen | permanent

@router.post("/emails/bulk-delete")
def bulk_delete_email_logs(payload: BulkDeleteRequest, db: Session = Depends(get_db)):
    """Bulk delete multiple log entries with optional IMAP action."""
    deleted = []
    for log_id in payload.ids:
        log = db.query(EmailAnalysisLog).filter(EmailAnalysisLog.id == log_id).first()
        if log:
            _imap_action_on_uid(log.message_id, payload.mode)
            db.delete(log)
            deleted.append(log_id)
    db.commit()
    return {"status": "deleted", "count": len(deleted), "ids": deleted, "mode": payload.mode}


# ── PATCH /emails/{id}/feedback ─────────────────────────────────────────────
@router.patch("/emails/{log_id}/feedback")
def submit_feedback(log_id: int, feedback: FeedbackUpdate, db: Session = Depends(get_db)):
    """Submit human feedback on an AI verdict for few-shot learning."""
    log = db.query(EmailAnalysisLog).filter(EmailAnalysisLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Log entry not found")
    log.user_feedback = feedback.user_feedback
    log.user_notes = feedback.user_notes
    db.commit()
    return {"status": "feedback saved", "id": log_id, "feedback": feedback.user_feedback}


# ── GET /system ──────────────────────────────────────────────────────────────
@router.get("/system", response_model=List[SystemLogResponse])
def get_system_logs(limit: int = 100, skip: int = 0, db: Session = Depends(get_db)):
    """Backend internal tracking logs."""
    return db.query(SystemLog).order_by(SystemLog.timestamp.desc()).offset(skip).limit(limit).all()


# ── GET /stats ───────────────────────────────────────────────────────────────
@router.get("/stats")
def get_usage_stats(db: Session = Depends(get_db)):
    """Global usage statistics."""
    from sqlalchemy import func
    total_emails    = db.query(EmailAnalysisLog).count()
    total_phishing  = db.query(EmailAnalysisLog).filter(EmailAnalysisLog.is_fraudulent == True).count()
    total_safe      = db.query(EmailAnalysisLog).filter(EmailAnalysisLog.is_fraudulent == False).count()
    prompt_tokens   = db.query(func.sum(EmailAnalysisLog.prompt_tokens)).scalar() or 0
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
