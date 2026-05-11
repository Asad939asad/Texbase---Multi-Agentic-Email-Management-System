import json
import base64
import os
import re
import sqlite3
from datetime import datetime, timedelta
from email.message import EmailMessage
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import random
import string
from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.environ.get('WORKSPACE_ROOT', '.'), 'backend/.env'))

# ==========================================
# APP CREDENTIALS (From your server.ts)
# ==========================================
CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')


def send_email_from_database(db_row_data, database_file='database.json', existing_unique_id=None):
    """
    Constructs and sends an email using credentials dynamically loaded 
    from database.json, then saves the record to a follow-ups database.
    """
    try:
        # 1. Load User Credentials from database.json
        if not os.path.exists(database_file):
            print(f"Error: Could not find {database_file}")
            return
            
        with open(database_file, 'r') as f:
            user_db_data = json.load(f)
            
        access_token = user_db_data.get('access_token')
        refresh_token = user_db_data.get('refresh_token') 
        sender_email = user_db_data.get('email')

        # 2. Parse the target Email JSON from the database row
        body_json_str = db_row_data.get('body_json', '{}')
        data = json.loads(body_json_str)
        
        # Extract necessary nested data
        body_data = data.get('body', {})
        generated_content = body_data.get('generated_content', '')
        
        # Support both 'outreach_data' (new) and 'excel_data' (old)
        outreach_data = body_data.get('outreach_data', body_data.get('excel_data', {}))
        
        # Prioritize the flat database column (sanitized by UI) over the JSON blob
        db_email = db_row_data.get('company_email')
        recipient_email = db_email if db_email and db_email != 'not updated' else outreach_data.get('company_email')
        
        if not recipient_email or not isinstance(recipient_email, str):
            print(f"❌ Error: Invalid recipient email type: {type(recipient_email)} content: {recipient_email}")
            return None
            
        # Robust cleaning: remove anything that isn't a valid email character
        recipient_email = "".join(c for c in recipient_email if c.isprintable()).strip().strip(',')
        
        if '@' not in recipient_email:
            print(f"❌ Error: Malformed email address: '{recipient_email}'")
            return None

        company_name    = outreach_data.get('company_name', db_row_data.get('company_name', 'Unknown Company'))
        
        # 3. Extract the Subject and HTML Body
        subject = body_data.get('subject', db_row_data.get('generated_subject', "Partnership Inquiry"))
        html_body = generated_content
        
        # If the generated content has a Subject: header, parse it
        match = re.match(r"(?i)Subject:\s*(.*?)(?:<br\s*/?>|\n)+(.*)", generated_content, re.DOTALL)
        if match:
            subject = match.group(1).strip()
            html_body = match.group(2).strip()

        # Final sanitization of headers to prevent "Invalid Header" errors
        subject = subject.replace('\n', ' ').replace('\r', ' ').strip()
        recipient_email = recipient_email.strip()

        # 4. Authenticate
        creds = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=CLIENT_ID,         # <-- Added
            client_secret=CLIENT_SECRET, # <-- Added
            scopes=["https://www.googleapis.com/auth/gmail.send"]
        )

        # Force a token refresh if it has expired
        if creds and creds.expired and creds.refresh_token:
            print("Access token expired. Refreshing token automatically...")
            creds.refresh(Request())
            
            # Optional: You could write the newly refreshed access_token back to your database.json here 
            # so the next run is faster, but it's not strictly necessary since the library handles it in memory!

        # 5. Construct the Email Message
        message = EmailMessage()
        message["To"] = recipient_email
        message["From"] = sender_email.strip() if sender_email else ""
        message["Subject"] = subject
        
        # --- Robust HTML Formatting ---
        if '<p>' not in html_body and '<br' not in html_body:
            # Handle Markdown-style bolding **text** -> <b>text</b>
            html_body = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", html_body)
            
            # Handle Markdown-style bullet points - text -> • text
            lines = html_body.split('\n')
            for i, line in enumerate(lines):
                s_line = line.strip()
                if s_line.startswith('- '):
                    lines[i] = '• ' + s_line[2:]
            html_body = '\n'.join(lines)

            # Split by double newline for paragraphs
            paragraphs = [p.strip() for p in html_body.split('\n\n') if p.strip()]
            if len(paragraphs) > 1:
                html_body = "".join("<p style='margin-bottom:1.2em;'>" + p.replace('\n', '<br />') + "</p>" for p in paragraphs)
            else:
                html_body = html_body.replace('\n', '<br />')
        elif '\n' in html_body and not html_body.startswith('<'):
            # Fallback for mixed content
            html_body = html_body.replace('\n', '<br />')

        # Final HTML wrapper for professional look
        html_wrapper = f"""
        <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #1f2937; max-width: 600px;">
            {html_body}
        </div>
        """
            
        message.set_content(html_wrapper, subtype='html')

        # 6. Optional: Attach documents (omitted for standard B2B outreach unless specified)
        # If we had a brochure_path, we would attach it here.

        # 7. Send the Email via Gmail API
        service = build('gmail', 'v1', credentials=creds)
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        
        sent_message = service.users().messages().send(
            userId="me", 
            body={'raw': raw_message}
        ).execute()
        
        print(f"Email sent successfully to {recipient_email}. Message ID: {sent_message['id']}")

        # 8. Save to Follow-Ups Database
        save_to_followups_db(recipient_email, company_name, subject, body_json_str, sent_message['id'], existing_unique_id)

        return sent_message

    except HttpError as error:
        print(f"Gmail API Error: {error}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


def save_to_followups_db(company_email, company_name, subject, body_json_str, message_id, existing_unique_id=None):
    """
    Saves or updates the sent email details into the master outreach journey database.
    If existing_unique_id is provided, it updates the record. Otherwise, it creates a new one.
    """
    base_dir = os.path.join(os.environ.get('WORKSPACE_ROOT', '.'), 'Database/FollowUps')
    os.makedirs(base_dir, exist_ok=True) 
    db_path = os.path.join(base_dir, 'sent_emails.db')

    now = datetime.now()
    followup_time = now + timedelta(days=7)

    # Use existing ID or generate a new random 20-digit ID
    unique_id = existing_unique_id if existing_unique_id else ''.join(random.choices(string.digits, k=20))

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sent_applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_email TEXT,
                company_name TEXT,
                generated_subject TEXT,
                date_sent DATETIME,
                followup_date DATETIME,
                status TEXT,
                Unique_application_id TEXT,
                message_id TEXT,
                body_json TEXT
            )
        ''')

        # Check if record exists
        cursor.execute("SELECT id FROM sent_applications WHERE Unique_application_id = ?", (unique_id,))
        exists = cursor.fetchone()

        if exists:
            # Update existing record (Follow-up case)
            cursor.execute('''
                UPDATE sent_applications 
                SET date_sent = ?, followup_date = ?, status = ?, message_id = ?, body_json = ?, generated_subject = ?
                WHERE Unique_application_id = ?
            ''', (
                now.strftime("%Y-%m-%d %H:%M:%S"),
                followup_time.strftime("%Y-%m-%d %H:%M:%S"),
                "Follow-up Sent - Awaiting Reply",
                message_id,
                body_json_str,
                subject,
                unique_id
            ))
            print(f"Follow-up logged. Journey updated for ID: {unique_id}")
        else:
            # Create new record (Cold email case)
            cursor.execute('''
                INSERT INTO sent_applications 
                (company_email, company_name, generated_subject, date_sent, followup_date, status, Unique_application_id, message_id, body_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                company_email, 
                company_name,
                subject,
                now.strftime("%Y-%m-%d %H:%M:%S"), 
                followup_time.strftime("%Y-%m-%d %H:%M:%S"), 
                "Sent - Awaiting Follow-up",
                unique_id,
                message_id,
                body_json_str
            ))
            print(f"New application logged. ID: {unique_id}")

        conn.commit()

    except sqlite3.Error as e:
        print(f"Database error occurred: {e}")
    finally:
        if conn:
            conn.close()

# ==========================================
# Example Usage
# ==========================================
if __name__ == "__main__":
    
    sample_db_row = {
        "body_json": """{
          "body": {
            "generated_content": "Subject: Excited About Stripe's Mission and Eager to Contribute<br><br>Hi Stripe Team,<br><br>I hope this email finds you well. I’ve been following Stripe’s journey and am genuinely impressed by how you’ve built the financial infrastructure for the internet. Your mission to simplify global payments and empower businesses of all sizes resonates deeply with me. I’d love to be part of a team that’s making such a significant impact on the internet economy.<br><br>As a final-year AI student at GIKI, I’ve developed a strong foundation in building scalable systems and solving complex problems. My work often involves critical thinking and thorough research, which aligns well with Stripe’s focus on reliability and developer-friendly infrastructure. I’m particularly drawn to your vision of enabling businesses to innovate faster and reach customers worldwide, and I believe my skills and passion could contribute meaningfully to this goal.<br><br>I’ve shared some of my projects and contributions on my GitHub (https://github.com) and LinkedIn (https://linkedin.com). I’d love to connect and discuss how I can bring value to Stripe’s mission. Looking forward to the possibility of collaborating with such an inspiring team.<br><br>Best regards,<br>Asad Irfan",
            "excel_data": {
              "company_email": "u2022120@gmail.com",
              "role": "Software Engineer"
            }
          }
        }"""
    }

    # Execute the function
    path_ = os.path.join(os.getcwd(), 'backend/database.json')
    # send_email_from_database(sample_db_row, path_)