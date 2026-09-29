import os
import time
import json
import base64
import argparse
from datetime import datetime, timezone
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from storage import init_db, is_email_processed, mark_email_processed
from pipeline import process_document

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
DEFAULT_QUERY = 'has:attachment (subject:invoice OR subject:receipt OR subject:statement OR filename:pdf OR filename:png OR filename:jpg)'
VALID_EXTENSIONS = ('.pdf', '.png', '.jpg', '.jpeg')

def get_gmail_service(credentials_path: str = 'credentials.json', token_path: str = 'token.json'):
    """
    Authenticates and returns the Gmail API service instance.
    Handles token refresh or initiates OAuth2 browser flow if needed.
    """
    creds = None
    if os.path.exists(token_path):
        try:
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        except Exception as e:
            print(f"[EmailIngestor] Warning: Failed to load token from {token_path}: {e}")
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"[EmailIngestor] Warning: Failed to refresh access token: {e}")
                creds = None
        
        if not creds:
            if not os.path.exists(credentials_path):
                raise FileNotFoundError(
                    f"OAuth credentials file missing at '{credentials_path}'. "
                    "Please download client_secret.json from Google Cloud Console as credentials.json."
                )
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save credentials for future runs
        with open(token_path, 'w') as token_file:
            token_file.write(creds.to_json())

    return build('gmail', 'v1', credentials=creds)

def parse_email_headers(headers: list) -> dict:
    """Extracts Subject, From, and Date headers from Gmail API payload headers."""
    header_dict = {h['name'].lower(): h['value'] for h in headers if 'name' in h and 'value' in h}
    sender = header_dict.get('from', 'unknown@example.com')
    subject = header_dict.get('subject', 'No Subject')
    date_str = header_dict.get('date', '')
    return {
        'sender': sender,
        'subject': subject,
        'received_date': date_str or datetime.now(timezone.utc).isoformat()
    }

def download_attachment(service, user_id: str, message_id: str, attachment_id: str, filename: str, output_dir: str) -> str:
    """Downloads attachment binary data from Gmail API and saves to disk."""
    try:
        attachment = service.users().messages().attachments().get(
            userId=user_id, messageId=message_id, id=attachment_id
        ).execute()

        file_data = base64.urlsafe_b64decode(attachment['data'].encode('UTF-8'))
        os.makedirs(output_dir, exist_ok=True)
        save_path = os.path.join(output_dir, f"{message_id}_{filename}")
        
        with open(save_path, 'wb') as f:
            f.write(file_data)
            
        return save_path
    except Exception as e:
        print(f"[EmailIngestor] Error downloading attachment {filename} from message {message_id}: {e}")
        return None

def process_single_message(service, message_id: str, output_dir: str):
    """Processes a single Gmail message: extracts attachments and routes to pipeline."""
    if is_email_processed(message_id):
        print(f"[EmailIngestor] Skipping already processed message_id: {message_id}")
        return

    try:
        msg = service.users().messages().get(userId='me', id=message_id, format='full').execute()
        payload = msg.get('payload', {})
        headers = payload.get('headers', [])
        meta = parse_email_headers(headers)
        meta['message_id'] = message_id

        parts = payload.get('parts', [])
        if not parts and payload.get('body', {}).get('attachmentId'):
            parts = [payload]

        attachment_found = False

        # Recursively walk MIME parts
        def walk_parts(mime_parts):
            nonlocal attachment_found
            for part in mime_parts:
                filename = part.get('filename')
                mime_type = part.get('mimeType', '')
                body = part.get('body', {})
                attachment_id = body.get('attachmentId')

                if part.get('parts'):
                    walk_parts(part.get('parts'))

                if filename and attachment_id and filename.lower().endswith(VALID_EXTENSIONS):
                    print(f"[EmailIngestor] Found valid attachment '{filename}' in email '{meta['subject']}'")
                    save_path = download_attachment(service, 'me', message_id, attachment_id, filename, output_dir)
                    if save_path:
                        attachment_found = True
                        process_document(save_path, meta)

        walk_parts(parts)

        # Mark message as processed even if no attachments matched so we don't scan it again
        mark_email_processed(message_id, meta['subject'], meta['sender'])

    except Exception as e:
        print(f"[EmailIngestor] Recoverable error processing message {message_id}: {e}")

def run_email_poll(service, query: str, output_dir: str):
    """Polls Gmail for matching messages and ingests new attachments."""
    print(f"[EmailIngestor] Querying Gmail for: '{query}'...")
    try:
        response = service.users().messages().list(userId='me', q=query).execute()
        messages = response.get('messages', [])
        
        if not messages:
            print("[EmailIngestor] No matching emails found.")
            return

        print(f"[EmailIngestor] Found {len(messages)} matching email(s). Processing...")
        for msg in messages:
            process_single_message(service, msg['id'], output_dir)

    except HttpError as e:
        print(f"[EmailIngestor] Gmail API HTTP error: {e}")
    except Exception as e:
        print(f"[EmailIngestor] Unexpected error during poll cycle: {e}")

def run_mock_ingestion(output_dir: str):
    """Simulates an email ingestion run for test/demo environments without live Gmail credentials."""
    print("[EmailIngestor] Running in MOCK test mode...")
    os.makedirs(output_dir, exist_ok=True)
    mock_msg_id = f"mock_msg_{int(time.time())}"
    
    sample_file = os.path.join(output_dir, f"{mock_msg_id}_sample_invoice.pdf")
    try:
        from reportlab.pdfgen import canvas
        c = canvas.Canvas(sample_file)
        c.drawString(100, 750, "INVOICE #9988")
        c.drawString(100, 730, "Vendor: Mock Email Ingestion Inc")
        c.drawString(100, 710, "Total: 1500.00 USD")
        c.drawString(100, 690, "Date: 2026-07-22")
        c.save()
    except Exception as e:
        print(f"[EmailIngestor] PDF generation failed: {e}")
        sample_file = os.path.join(output_dir, f"{mock_msg_id}_sample_invoice.txt")
        with open(sample_file, "w") as f:
            f.write("INVOICE #9988\nVendor: Mock Email Ingestion Inc\nTotal: 1500.00 USD\nDate: 2026-07-22")
        
    metadata = {
        "sender": "billing@vendor-mock.com",
        "subject": "Invoice #9988 for Services",
        "received_date": datetime.now(timezone.utc).isoformat(),
        "message_id": mock_msg_id
    }
    
    print(f"[EmailIngestor] Created mock email attachment at {sample_file}")
    process_document(sample_file, metadata)
    mark_email_processed(mock_msg_id, metadata['subject'], metadata['sender'])
    print("[EmailIngestor] Mock email ingestion complete.")

def main():
    parser = argparse.ArgumentParser(description="Gmail Document Ingestor Poller")
    parser.add_argument("--query", default=DEFAULT_QUERY, help="Gmail search query for filtering emails")
    parser.add_argument("--poll-interval", type=int, default=0, help="Poll interval in seconds (0 = single pass)")
    parser.add_argument("--output-dir", default="input_docs", help="Target folder to save extracted attachments")
    parser.add_argument("--credentials", default="credentials.json", help="Path to Google OAuth client secret JSON")
    parser.add_argument("--token", default="token.json", help="Path to save OAuth token JSON")
    parser.add_argument("--mock-test", action="store_true", help="Run mock ingestion without Gmail credentials")

    args = parser.parse_args()
    init_db()

    if args.mock_test:
        run_mock_ingestion(args.output_dir)
        return

    try:
        service = get_gmail_service(args.credentials, args.token)
    except Exception as e:
        print(f"[EmailIngestor] Authentication failed: {e}")
        print("[EmailIngestor] To test without credentials, run with --mock-test flag.")
        return

    if args.poll_interval <= 0:
        run_email_poll(service, args.query, args.output_dir)
    else:
        print(f"[EmailIngestor] Starting continuous poller loop (interval: {args.poll_interval}s)...")
        while True:
            run_email_poll(service, args.query, args.output_dir)
            time.sleep(args.poll_interval)

if __name__ == '__main__':
    main()
