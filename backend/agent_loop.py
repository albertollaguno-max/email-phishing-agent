import logging
import os
import re
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from database import SessionLocal, AllowedSender, EmailAnalysisLog, SystemLog, SenderType
from email_client import EmailClient
from ai_engine import analyze_email_content
from responder import send_response

logger = logging.getLogger(__name__)

CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", "5"))

def run_agent_loop():
    logger.info("Starting background agent loop execution...")
    db: Session = SessionLocal()
    try:
        # Load active allowed senders
        allowed_senders = db.query(AllowedSender).filter(AllowedSender.is_active == True).all()
        allowed_domains = [s.value.lower() for s in allowed_senders if s.type == SenderType.DOMAIN]
        allowed_emails = [s.value.lower() for s in allowed_senders if s.type == SenderType.EMAIL]

        if not allowed_domains and not allowed_emails:
            logger.warning("No allowed senders configured. Exiting loop step early.")
            return

        client = EmailClient()
        for msg in client.fetch_unseen_emails():
            print(f"DEBUG: Processing message {msg._uid}")
            try:
                # 1. Check if email was already processed in DB (using IMAP UID)
                msg_id = getattr(msg, '_uid', str(msg.uid))
                existing_log = db.query(EmailAnalysisLog).filter(EmailAnalysisLog.message_id == msg_id).first()
                if existing_log:
                    logger.info(f"Skipping already processed message {msg_id}")
                    print(f"DEBUG: Skipped existing msg {msg_id}")
                    continue
                
                # 2. Extract forwarder (the one who sent to the agent's IMAP box)
                forwarder_email = msg.from_values.email if msg.from_values else None
                print(f"DEBUG: Msg {msg.uid} forwarder is {forwarder_email}")
                if not forwarder_email:
                    logger.warning(f"Could not extract forwarder email from msg {msg.uid}")
                    continue
                
                forwarder_domain = forwarder_email.split('@')[-1].lower() if '@' in forwarder_email else ''
                forwarder_email_lower = forwarder_email.lower()

                # 3. Check if forwarder is allowed
                is_allowed = (forwarder_domain in allowed_domains) or (forwarder_email_lower in allowed_emails)
                print(f"DEBUG: Msg {msg.uid} forwarder allowed? {is_allowed}")
                if not is_allowed:
                    logger.info(f"Ignored unauthorized forwarder: {forwarder_email}")
                    continue

                # 4. Extract original sender from the email body (simplistic heuristic for forwarded emails)
                body_text = msg.text or msg.html or ""
                original_sender_match = re.search(r'From:\s*(.+?)\s*(\n|<)', body_text, re.IGNORECASE)
                original_sender = original_sender_match.group(1).strip() if original_sender_match else "unknown"

                logger.info(f"Processing allowed forwarded email from {forwarder_email} with subject '{msg.subject}'")
                print(f"DEBUG: Msg {msg.uid} matched. Calling AI for {msg.subject}...")

                # 5. Analyze with AI
                ai_result, p_tokens, c_tokens, provider = analyze_email_content(msg.subject, original_sender, body_text)
                print(f"DEBUG: Msg {msg.uid} AI result: {ai_result}")
                
                # 6. Save initial log
                log_entry = EmailAnalysisLog(
                    message_id=msg_id,
                    from_address=original_sender,
                    forwarded_by=forwarder_email,
                    subject=msg.subject,
                    date_received=msg.date,
                    is_fraudulent=ai_result.get('is_fraudulent'),
                    ai_explanation=ai_result.get('explanation'),
                    ai_provider_used=provider,
                    prompt_tokens=p_tokens,
                    completion_tokens=c_tokens,
                )
                db.add(log_entry)
                db.commit()

                # 7. Send Response
                resp_success = send_response(forwarder_email, msg.subject, ai_result)
                if resp_success:
                    from datetime import datetime
                    log_entry.response_sent_at = datetime.utcnow()
                    db.commit()

                sys_log = SystemLog(level="INFO", message=f"Successfully analyzed and responded to msg {msg.uid} fwd by {forwarder_email}")
                db.add(sys_log)
                db.commit()

            except Exception as e:
                logger.error(f"Error processing individual message {getattr(msg, 'uid', 'unknown')}: {e}")
                sys_log = SystemLog(level="ERROR", message=f"Error processing message {getattr(msg, 'uid', 'unknown')}: {str(e)}")
                db.add(sys_log)
                db.commit()

    except Exception as e:
         logger.error(f"Fatal error in background loop: {e}")
    finally:
         db.close()


def start_background_tasks():
    logger.info(f"Starting Background Scheduler every {CHECK_INTERVAL_MINUTES} minutes")
    scheduler = BackgroundScheduler()
    # Run once immediately
    from datetime import datetime
    scheduler.add_job(run_agent_loop, 'date', run_date=datetime.now())
    # Then schedule periodically
    scheduler.add_job(run_agent_loop, 'interval', minutes=CHECK_INTERVAL_MINUTES)
    scheduler.start()
    return scheduler
