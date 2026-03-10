import os
import smtplib
import email.utils
from email.message import EmailMessage
import logging
from dotenv import load_dotenv

load_dotenv()

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM_ADDRESS = os.getenv("SMTP_FROM_ADDRESS", SMTP_USER)
IMAP_HOST = os.getenv("IMAP_HOST")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))

logger = logging.getLogger(__name__)


def _sanitize_header(value: str) -> str:
    """Remove any newline/carriage return chars from email header values."""
    if not value:
        return value
    return value.replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ').strip()


def _save_to_sent(raw_msg_bytes: bytes):
    """Append the sent message to the Sent folder via IMAP so it shows in the webmail."""
    try:
        import imaplib
        import time
        with imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT) as imap:
            imap.login(SMTP_USER, SMTP_PASSWORD)
            sent_folder = "Elementos enviados"
            # Use imap.append() with explicit size literal
            result = imap.append(
                sent_folder,
                r'\Seen',
                imaplib.Time2Internaldate(time.time()),
                raw_msg_bytes
            )
            if result[0] == 'OK':
                logger.info(f"Message saved to '{sent_folder}' folder")
            else:
                logger.warning(f"Could not save to '{sent_folder}': {result}")
    except Exception as e:
        logger.warning(f"Could not save to Sent folder: {e}")


def send_response(to_address: str, original_subject: str, ai_result: dict):
    if not all([SMTP_HOST, SMTP_USER, SMTP_PASSWORD]):
        logger.error("SMTP credentials are not configured.")
        return False

    verdict = "🚨 ALERTA DE PHISHING" if ai_result.get("is_fraudulent") else "✅ CORREO SEGURO"
    confidence = ai_result.get("confidence_level", "unknown").upper()
    explanation = ai_result.get("explanation", "Sin explicación provista.")

    # Sanitize subject to avoid SMTP header injection errors
    clean_subject = _sanitize_header(original_subject)
    clean_to = _sanitize_header(to_address)

    msg = EmailMessage()
    msg['Subject'] = f"Re: {clean_subject} - Análisis: {verdict}"
    msg['From'] = SMTP_FROM_ADDRESS
    msg['To'] = clean_to
    msg['Date'] = email.utils.formatdate(localtime=True)

    html_content = f"""
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background-color: {'#ffebee' if ai_result.get('is_fraudulent') else '#e8f5e9'}; padding: 20px; border-radius: 8px; border: 1px solid {'#ef9a9a' if ai_result.get('is_fraudulent') else '#a5d6a7'}; margin-bottom: 20px;">
            <h2 style="margin-top: 0; color: {'#d32f2f' if ai_result.get('is_fraudulent') else '#2e7d32'};">{verdict}</h2>
            <p><strong>Nivel de Confianza:</strong> {confidence}</p>
            <p><strong>Análisis de la IA:</strong><br>{explanation}</p>
        </div>
        <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
        <p style="font-size: 12px; color: #888; text-align: center;">Este es un mensaje automático del Agente Detector de Phishing mediante IA.</p>
      </body>
    </html>
    """
    msg.set_content("Asegúrate de configurar tu cliente de correo para ver mensajes HTML.")
    msg.add_alternative(html_content, subtype='html')

    try:
        raw_bytes = msg.as_bytes()
        if SMTP_PORT == 465:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(msg)
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(msg)
        logger.info(f"Response sent to {clean_to} for subject '{clean_subject}'")

        # Save copy to Sent folder
        if IMAP_HOST:
            _save_to_sent(raw_bytes)

        return True
    except Exception as e:
        logger.error(f"Failed to send email to {clean_to}: {e}")
        return False


