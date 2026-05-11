import json
import os
import sqlite3
import re
from datetime import datetime
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import sys
import base64
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.environ.get('WORKSPACE_ROOT', '.'), 'backend/.env'))

CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
DATABASE_FILE = os.path.join(os.environ.get('WORKSPACE_ROOT', '.'), 'backend/database.json')
SENT_DB_PATH = os.path.join(os.environ.get('WORKSPACE_ROOT', '.'), 'Database/FollowUps/sent_emails.db')
QUEUE_DB_PATH = os.path.join(os.environ.get('WORKSPACE_ROOT', '.'), 'Database/EmailsSent/email_to_be_sent.db')
INBOX_DB_DIR = os.path.join(os.environ.get('WORKSPACE_ROOT', '.'), 'Database/Inbox')
INBOX_DB_PATH = os.path.join(INBOX_DB_DIR, 'inbox.db')

def init_db():
    os.makedirs(INBOX_DB_DIR, exist_ok=True)
    conn = sqlite3.connect(INBOX_DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inbox_threads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id TEXT UNIQUE,
            company_email TEXT,
            company_name TEXT,
            subject TEXT,
            last_messages_json TEXT,
            date_received DATETIME,
            status TEXT DEFAULT 'pending_reply'
        )
    ''')
    conn.commit()
    return conn

def get_contacted_emails():
    emails = {}
    
    # Check sent_emails.db
    if os.path.exists(SENT_DB_PATH):
        try:
            conn = sqlite3.connect(SENT_DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT company_email, company_name FROM sent_applications")
            for row in cursor.fetchall():
                email, name = row
                if email:
                    emails[email.strip().lower()] = name
            conn.close()
        except Exception as e:
            pass

    # Check email_to_be_sent.db as requested by user
    if os.path.exists(QUEUE_DB_PATH):
        try:
            conn = sqlite3.connect(QUEUE_DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT company_email, company_name FROM ready_emails")
            for row in cursor.fetchall():
                email, name = row
                if email:
                    emails[email.strip().lower()] = name
            conn.close()
        except Exception as e:
            pass

    return emails

def parse_email_address(header_val):
    if not header_val: return ""
    match = re.search(r'[\w\.-]+@[\w\.-]+', header_val)
    if match:
        return match.group(0).lower()
    return ""

def get_body(payload):
    body = ""
    if 'parts' in payload:
        for part in payload['parts']:
            if part['mimeType'] == 'text/plain':
                data = part['body'].get('data', '')
                if data:
                    try:
                        body += base64.urlsafe_b64decode(data).decode('utf-8')
                    except Exception:
                        pass
            elif 'parts' in part:
                body += get_body(part)
    elif payload.get('mimeType') == 'text/plain':
        data = payload['body'].get('data', '')
        if data:
            try:
                body += base64.urlsafe_b64decode(data).decode('utf-8')
            except Exception:
                pass
    return body

def fetch_inbox():
    if not os.path.exists(DATABASE_FILE):
        print(json.dumps({"error": f"Credentials {DATABASE_FILE} not found."}))
        return

    with open(DATABASE_FILE, 'r') as f:
        user_db_data = json.load(f)

    access_token = user_db_data.get('access_token')
    refresh_token = user_db_data.get('refresh_token')

    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        scopes=["https://www.googleapis.com/auth/gmail.modify"]
    )

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())

    service = build('gmail', 'v1', credentials=creds)
    conn = init_db()
    cursor = conn.cursor()

    contacted_emails = get_contacted_emails()

    try:
        # Fetch recent messages from Inbox
        results = service.users().messages().list(userId='me', labelIds=['INBOX'], maxResults=50).execute()
        messages = results.get('messages', [])
        
        fetched_count = 0
        new_threads = []

        for msg in messages:
            msg_id = msg['id']
            thread_id = msg['threadId']
            
            # Check if we already processed this thread
            cursor.execute("SELECT id FROM inbox_threads WHERE thread_id = ?", (thread_id,))
            if cursor.fetchone():
                continue

            # Fetch full message
            full_msg = service.users().messages().get(userId='me', id=msg_id, format='metadata', metadataHeaders=['From', 'Subject', 'Date']).execute()
            headers = full_msg.get('payload', {}).get('headers', [])
            
            from_email_header = next((h['value'] for h in headers if h['name'].lower() == 'from'), "")
            from_email = parse_email_address(from_email_header)
            subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), "No Subject")
            
            if from_email in contacted_emails:
                company_name = contacted_emails[from_email]
                
                # Fetch thread to get last 5 messages (format=full to get payload body)
                thread = service.users().threads().get(userId='me', id=thread_id, format='full').execute()
                thread_messages = thread.get('messages', [])
                
                # Extract text
                last_5 = thread_messages[-5:]
                history = []
                for t_msg in last_5:
                    t_payload = t_msg.get('payload', {})
                    t_headers = t_payload.get('headers', [])
                    t_from = next((h['value'] for h in t_headers if h['name'].lower() == 'from'), "")
                    t_date = next((h['value'] for h in t_headers if h['name'].lower() == 'date'), "")
                    
                    body_content = get_body(t_payload)
                    snippet = body_content.strip() if body_content else t_msg.get('snippet', '')
                    
                    history.append({
                        "from": t_from,
                        "date": t_date,
                        "snippet": snippet
                    })

                cursor.execute('''
                    INSERT INTO inbox_threads (thread_id, company_email, company_name, subject, last_messages_json, date_received)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (thread_id, from_email, company_name, subject, json.dumps(history), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                conn.commit()
                fetched_count += 1
                new_threads.append({
                    "thread_id": thread_id,
                    "company_email": from_email,
                    "subject": subject
                })

        print(json.dumps({"success": True, "fetched_count": fetched_count, "new_threads": new_threads}))

    except Exception as e:
        print(json.dumps({"error": str(e)}))

if __name__ == "__main__":
    fetch_inbox()
