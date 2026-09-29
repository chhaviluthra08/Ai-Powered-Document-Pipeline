import os
import time
import imaplib
import email
from email.header import decode_header
import hashlib
from datetime import datetime, timezone
from dotenv import load_dotenv

from storage import get_connection, is_email_processed, is_duplicate_document, compute_file_hash

load_dotenv()

MIN_ATTACHMENT_SIZE = 20 * 1024  # 20KB — filters out logos/icons/signature images

SKIP_FILENAME_PATTERNS = [
    'icon', 'logo', 'banner', 'social', 'facebook', 'twitter', 'instagram',
    'linkedin', 'youtube', 'glassdoor', 'ibm-black', 'ibm-logo'
]

def is_likely_document(filename: str, content_bytes: bytes) -> bool:
    """Filter out marketing/email-signature images that aren't real documents."""
    if not content_bytes or len(content_bytes) < MIN_ATTACHMENT_SIZE:
        return False
    lower_name = filename.lower()
    if any(pattern in lower_name for pattern in SKIP_FILENAME_PATTERNS):
        return False
    return True

VALID_EXTENSIONS = ('.pdf', '.png', '.jpg', '.jpeg')

def parse_header_str(header_val: str) -> str:
    """Decodes MIME encoded email header values into a standard Python string."""
    if not header_val:
        return ""
    decoded_parts = decode_header(header_val)
    header_str = ""
    for part, encoding in decoded_parts:
        if isinstance(part, bytes):
            header_str += part.decode(encoding or 'utf-8', errors='replace')
        else:
            header_str += str(part)
    return header_str.strip()

def fetch_unread_email_attachments(input_dir: str = "input_docs") -> list:
    """
    Connects to mailbox via IMAP using EMAIL_HOST, EMAIL_USER, EMAIL_PASSWORD, EMAIL_FOLDER env vars.
    Polls for UNSEEN emails containing qualifying attachments (PDF, PNG, JPG, JPEG).
    Saves attachments to input_dir, builds metadata matching process_document() contract,
    marks processed emails as \\Seen, and handles IMAP/network errors gracefully.
    
    Returns list of dicts: [{'file_path': str, 'metadata': dict}]
    """
    email_host = os.environ.get("EMAIL_HOST")
    email_user = os.environ.get("EMAIL_USER")
    email_password = os.environ.get("EMAIL_PASSWORD")
    email_folder = os.environ.get("EMAIL_FOLDER", "INBOX")

    if not email_host or not email_user or not email_password:
        print("[EmailIngestion] IMAP credentials missing in environment (EMAIL_HOST, EMAIL_USER, EMAIL_PASSWORD). Skipping email fetch.")
        return []

    documents = []
    os.makedirs(input_dir, exist_ok=True)

    try:
        print(f"[EmailIngestion] Connecting to IMAP host '{email_host}', folder '{email_folder}' as '{email_user}'...")
        mail = imaplib.IMAP4_SSL(email_host)
        mail.login(email_user, email_password)
        mail.select(email_folder)

        status, response = mail.search(None, 'UNSEEN')
        if status != 'OK' or not response or not response[0]:
            print("[EmailIngestion] No unread emails found.")
            mail.logout()
            return documents

        msg_ids = response[0].split()
        print(f"[EmailIngestion] Found {len(msg_ids)} unread email(s). Processing...")

        for msg_id_bytes in msg_ids:
            try:
                res_status, msg_data = mail.fetch(msg_id_bytes, '(RFC822)')
                if res_status != 'OK' or not msg_data:
                    continue

                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                message_id = parse_header_str(msg.get("Message-ID", f"msg_{msg_id_bytes.decode()}"))
                sender = parse_header_str(msg.get("From", "unknown@example.com"))
                subject = parse_header_str(msg.get("Subject", "No Subject"))
                date_str = msg.get("Date", "")

                # Check if email message_id already processed in DB
                if message_id and is_email_processed(message_id):
                    print(f"[EmailIngestion] Skipping email message_id '{message_id}' (already processed).")
                    mail.store(msg_id_bytes, '+FLAGS', '\\Seen')
                    continue

                metadata = {
                    "sender": sender,
                    "subject": subject,
                    "received_date": date_str or datetime.now(timezone.utc).isoformat(),
                    "message_id": message_id
                }

                attachment_found = False

                for part in msg.walk():
                    content_disposition = str(part.get("Content-Disposition", ""))
                    filename = part.get_filename()

                    if filename:
                        filename = parse_header_str(filename)

                    if "attachment" in content_disposition.lower() or filename:
                        if filename and filename.lower().endswith(VALID_EXTENSIONS):
                            payload = part.get_payload(decode=True)
                            if not payload:
                                continue

                            if not is_likely_document(filename, payload):
                                print(f"[EmailIngestion] Skipping non-document attachment '{filename}' (size/pattern filter)")
                                continue

                            # Save attachment to input_dir
                            safe_filename = "".join(c for c in filename if c.isalnum() or c in "._- ")
                            file_save_path = os.path.join(input_dir, f"{message_id[:8]}_{safe_filename}")

                            with open(file_save_path, "wb") as f:
                                f.write(payload)

                            file_hash = compute_file_hash(file_save_path)
                            if is_duplicate_document(file_hash):
                                print(f"[EmailIngestion] Skipping attachment '{filename}' (content hash already exists).")
                                continue

                            attachment_found = True
                            print(f"[EmailIngestion] Saved attachment '{safe_filename}' from email '{subject}'")
                            documents.append({
                                "file_path": file_save_path,
                                "metadata": metadata
                            })

                # Mark email as read so it isn't re-ingested
                mail.store(msg_id_bytes, '+FLAGS', '\\Seen')

            except Exception as single_msg_err:
                print(f"[EmailIngestion] Recoverable error processing email {msg_id_bytes}: {single_msg_err}")
                continue

        mail.logout()

    except Exception as network_err:
        print(f"[EmailIngestion] Network / IMAP connection error: {network_err}")

    return documents

def run_email_poller(poll_interval: int = 60, input_dir: str = "input_docs", callback=None):
    """
    Continuous background polling loop for email auto-ingestion.
    Periodically fetches unread email attachments and executes callback (e.g. process_document).
    """
    print(f"[EmailIngestion] Starting continuous poller loop (interval: {poll_interval}s)...")
    while True:
        try:
            docs = fetch_unread_email_attachments(input_dir)
            if docs and callback:
                for doc in docs:
                    callback(doc['file_path'], doc['metadata'])
        except Exception as e:
            print(f"[EmailIngestion] Poller error: {e}")
        
        if poll_interval <= 0:
            break
        time.sleep(poll_interval)

if __name__ == '__main__':
    fetched = fetch_unread_email_attachments()
    print(f"[EmailIngestion] Fetched {len(fetched)} attachment(s).")
