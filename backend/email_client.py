import os
import logging
import imaplib
import email as email_lib
from imap_tools import MailMessage
from dotenv import load_dotenv

load_dotenv()

IMAP_HOST = os.getenv("IMAP_HOST")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
IMAP_USER = os.getenv("IMAP_USER")
IMAP_PASSWORD = os.getenv("IMAP_PASSWORD")

logger = logging.getLogger(__name__)


class EmailClient:
    def __init__(self):
        self.host = IMAP_HOST
        self.port = IMAP_PORT
        self.user = IMAP_USER
        self.password = IMAP_PASSWORD

    def fetch_unseen_emails(self):
        """Fetch unseen emails from INBOX and Spam using raw IMAP UIDs."""
        FOLDERS_TO_CHECK = ['INBOX', 'Spam']

        for folder_name in FOLDERS_TO_CHECK:
            try:
                with imaplib.IMAP4_SSL(self.host, self.port) as imap:
                    imap.login(self.user, self.password)
                    imap.select(folder_name)

                    # Search for UNSEEN messages by UID
                    typ, data = imap.uid('search', None, 'UNSEEN')
                    if typ != 'OK':
                        logger.warning(f"Could not search {folder_name}: {typ}")
                        continue

                    uid_list = data[0].decode().split()
                    logger.info(f"Folder '{folder_name}': {len(uid_list)} UNSEEN UIDs: {uid_list}")

                    for uid_bytes in uid_list[:20]:  # limit 20
                        uid = uid_bytes.strip()
                        # Fetch the raw message
                        typ2, msg_data = imap.uid('fetch', uid, '(RFC822)')
                        if typ2 != 'OK' or not msg_data or not msg_data[0]:
                            logger.warning(f"Could not fetch UID {uid}")
                            continue

                        raw_email = msg_data[0][1]
                        # Parse with imap_tools for compatibility with the rest of the code
                        msg = MailMessage.from_bytes(raw_email)
                        # Inject the UID so agent_loop can use it as message_id
                        msg._uid = uid.decode() if isinstance(uid, bytes) else uid

                        logger.info(f"YIELDING UID {uid} from '{folder_name}': {msg.subject[:60] if msg.subject else '(no subject)'}")
                        yield msg

                        # Mark as Seen AFTER yielding (once processed)
                        imap.uid('store', uid, '+FLAGS', '\\Seen')

            except Exception as e:
                logger.error(f"Error fetching from folder '{folder_name}': {e}")


