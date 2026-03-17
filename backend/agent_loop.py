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


def _extract_original_sender(msg, body_text: str, body_html: str) -> str:
    """
    Try to extract the original sender from a forwarded email.
    Handles: Outlook, Gmail, iOS Mail, Thunderbird, plain text.
    Returns the best match found or 'unknown'.
    """
    import html as html_module
    from email.utils import parseaddr

    # --- Strategy 1: imap_tools parsed headers (works if client embeds original as attachment) ---
    # Check if there are embedded message headers (Outlook sometimes does this)
    try:
        for part in (msg.attachments or []):
            if hasattr(part, 'filename') and part.filename and 'message' in part.filename.lower():
                pass  # Could extract from embedded message, skip for now
    except Exception:
        pass

    # --- Strategy 2: Parse plain text body ---
    # Patterns cover: Outlook EN/ES, Gmail EN/ES, iOS, Thunderbird, generic
    text_patterns = [
        # Outlook-style:  From: Name <email@domain.com>
        r'(?:^|\n)[ \t]*De:\s*(.+?)\s*(?:\n|$)',        # Outlook ES
        r'(?:^|\n)[ \t]*From:\s*(.+?)\s*(?:\n|$)',      # Outlook EN / generic
        r'(?:^|\n)[ \t]*Von:\s*(.+?)\s*(?:\n|$)',       # Outlook DE
        # Gmail forwarded block header: "---------- Forwarded message ---------\nFrom: ..."
        r'Forwarded message[\s\S]{0,200}?From:\s*(.+?)\n',
        r'mensaje reenviado[\s\S]{0,200}?De:\s*(.+?)\n',
        # Outlook RV: (reenvío) format - common in Spanish Outlook
        r'(?:^|\n)[ \t]*Enviado:\s*(.+?)\s*(?:\n|$)',   # Outlook ES alternate
        r'(?:^|\n)[ \t]*Sent:\s*(.+?)\s*(?:\n|$)',      # Outlook EN alternate
    ]

    # Also look for the sender in Outlook block format:
    # De: Name <email>
    # Enviado el: date
    # Para: recipient
    # Asunto: subject
    outlook_block_patterns = [
        r'De:\s*(.+?)\s*\n\s*(?:Enviado|Sent|Fecha)',
        r'From:\s*(.+?)\s*\n\s*(?:Sent|Date)',
        r'De:\s*([^\n]*?<[^>]+>)',
        r'From:\s*([^\n]*?<[^>]+>)',
    ]
    # Try Outlook block patterns first (more specific)
    for pattern in outlook_block_patterns:
        m = re.search(pattern, body_text, re.IGNORECASE | re.MULTILINE)
        if m:
            raw = m.group(1).strip()
            name, addr = parseaddr(raw)
            if addr and '@' in addr:
                return f"{name} <{addr}>" if name else addr
            if raw:
                return raw[:200]

    for pattern in text_patterns:
        m = re.search(pattern, body_text, re.IGNORECASE | re.MULTILINE)
        if m:
            raw = m.group(1).strip()
            # parseaddr handles both 'Name <email>' and bare emails
            name, addr = parseaddr(raw)
            if addr and '@' in addr:
                return f"{name} <{addr}>" if name else addr
            if raw:  # Return as-is even without a valid email
                return raw[:200]

    # --- Strategy 3: Search inside HTML (strip tags first) ---
    if body_html:
        # Remove HTML tags
        clean = re.sub(r'<[^>]+>', ' ', body_html)
        clean = html_module.unescape(clean)
        # Try Outlook block patterns first
        for pattern in outlook_block_patterns:
            m = re.search(pattern, clean, re.IGNORECASE | re.MULTILINE)
            if m:
                raw = m.group(1).strip()
                name, addr = parseaddr(raw)
                if addr and '@' in addr:
                    return f"{name} <{addr}>" if name else addr
                if raw:
                    return raw[:200]
        for pattern in text_patterns:
            m = re.search(pattern, clean, re.IGNORECASE | re.MULTILINE)
            if m:
                raw = m.group(1).strip()
                name, addr = parseaddr(raw)
                if addr and '@' in addr:
                    return f"{name} <{addr}>" if name else addr
                if raw:
                    return raw[:200]

    # --- Strategy 4: Any email address in the body that's not the forwarder ---
    # Pick first email-looking string found in body
    all_emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.]+', body_text or body_html)
    for candidate in all_emails:
        return candidate  # Return the first one found

    return "unknown"

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

        # Load last N human-corrected examples for few-shot learning (max 8 to keep prompt size reasonable)
        feedback_examples = []
        corrected_logs = (
            db.query(EmailAnalysisLog)
            .filter(EmailAnalysisLog.user_feedback.isnot(None))
            .order_by(EmailAnalysisLog.date_received.desc())
            .limit(8)
            .all()
        )
        for cl in corrected_logs:
            # When user marked 'incorrect', the real verdict is the opposite of what AI said
            real_is_fraudulent = cl.is_fraudulent
            if cl.user_feedback == 'incorrect':
                real_is_fraudulent = not cl.is_fraudulent
            feedback_examples.append({
                'subject': cl.subject or '',
                'sender': cl.from_address or '',
                'body': cl.body_text or '',  # Now includes real body from DB
                'is_fraudulent': real_is_fraudulent,
                'explanation': cl.ai_explanation or ''
            })

        if feedback_examples:
            logger.info(f"Loaded {len(feedback_examples)} feedback examples for few-shot learning")

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

                # 4. Extract original sender from forwarded content
                # Strategy: try multiple forwarding formats before falling back
                body_text = msg.text or ""
                body_html = msg.html or ""

                original_sender = _extract_original_sender(msg, body_text, body_html)

                logger.info(f"Processing allowed forwarded email from {forwarder_email} with subject '{msg.subject}'")
                print(f"DEBUG: Msg {msg.uid} matched. Calling AI for {msg.subject}...")

                # 4b. Extract attachment names and email headers for heuristic analysis
                attachment_names = []
                try:
                    for att in (msg.attachments or []):
                        if hasattr(att, 'filename') and att.filename:
                            attachment_names.append(att.filename)
                except Exception:
                    pass

                email_headers = {}
                try:
                    if hasattr(msg, 'headers') and msg.headers:
                        # imap_tools returns headers as CIMultiDict where values may be
                        # lists or tuples. Normalize to {key: first_value_as_str}.
                        for k, v in msg.headers.items():
                            key = k.lower()
                            val = v[0] if isinstance(v, (list, tuple)) else v
                            email_headers[key] = str(val) if val is not None else ''
                except Exception:
                    pass

                # 5. Analyze with AI (passing feedback examples + heuristic data)
                ai_result, p_tokens, c_tokens, provider = analyze_email_content(
                    msg.subject, original_sender, body_text or body_html,
                    feedback_examples=feedback_examples if feedback_examples else None,
                    body_html=body_html,
                    attachment_names=attachment_names if attachment_names else None,
                    email_headers=email_headers if email_headers else None,
                )
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
                    body_text=body_text[:65000] if body_text else None,  # Truncate to fit TEXT column
                    body_html=body_html[:65000] if body_html else None,
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
