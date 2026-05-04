import sys
import json
import sqlite3
import os
import random
import string
from datetime import datetime
from dotenv import load_dotenv
from azure.ai.inference import ChatCompletionsClient
from azure.core.credentials import AzureKeyCredential

load_dotenv(dotenv_path=os.path.join(os.environ.get('WORKSPACE_ROOT', os.path.join(os.environ.get('WORKSPACE_ROOT', '.'), 'backend/.env'))))

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
INBOX_DB = os.path.join(os.environ.get('WORKSPACE_ROOT', os.path.join(os.environ.get('WORKSPACE_ROOT', '.'), 'Database/Inbox/inbox.db')))
REVIEW_DB = os.path.join(os.environ.get('WORKSPACE_ROOT', os.path.join(os.environ.get('WORKSPACE_ROOT', '.'), 'Database/EmailsUnderReview/emailsUnderReview.db')))

SENDER = {
    "company": "Arooj Enterprises",
    "name":    "Asad Irfan",
    "title":   "Senior Marketing Manager",
    "website": "www.texbase.com",
    "certs":   "ISO 14001, SEDEX, and OEKO-TEX",
    "capacity": "150,000 units/month"
}

def init_review_db():
    conn = sqlite3.connect(REVIEW_DB)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tracking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT,
            website TEXT,
            address TEXT,
            total_shipments TEXT,
            top_suppliers TEXT,
            hs_codes TEXT,
            company_description TEXT,
            key_executives TEXT,
            generated_subject TEXT,
            status TEXT DEFAULT 'pending',
            body_json TEXT,
            company_email TEXT,
            deep_research_pdf TEXT
        )
    ''')
    conn.commit()
    return conn

def draft_reply(inbox_id):
    if not GITHUB_TOKEN:
        print(json.dumps({"error": "GITHUB_TOKEN not found."}))
        return

    # 1. Fetch thread history
    conn_inbox = sqlite3.connect(INBOX_DB)
    c_inbox = conn_inbox.cursor()
    c_inbox.execute("SELECT thread_id, company_email, company_name, subject, last_messages_json FROM inbox_threads WHERE id = ?", (inbox_id,))
    row = c_inbox.fetchone()
    
    if not row:
        print(json.dumps({"error": f"Inbox thread {inbox_id} not found."}))
        return

    thread_id, company_email, company_name, subject, last_messages_json = row
    history = json.loads(last_messages_json)

    history_text = "\n\n".join([f"From: {msg['from']}\nDate: {msg['date']}\nMessage:\n{msg['snippet']}" for msg in history])

    # 2. Call LLM
    client = ChatCompletionsClient(
        endpoint="https://models.github.ai/inference",
        credential=AzureKeyCredential(GITHUB_TOKEN),
    )

    prompt = f"""You are an expert B2B sales email writer for {SENDER['company']}.
You are replying to an email thread with {company_name} ({company_email}).

═══ EMAIL THREAD HISTORY ═══
{history_text}

═══ INSTRUCTIONS ═══
- Write a professional, concise, and persuasive reply to the most recent message in the thread.
- Address their questions or concerns directly.
- Maintain our company persona: we are a garment manufacturer from Pakistan with a capacity of {SENDER['capacity']} and certifications {SENDER['certs']}.
- Keep it under 150 words.
- Structure it cleanly with paragraphs separated by \\n\\n.

CRITICAL OUTPUT REQUIREMENT:
- Output strictly valid JSON with exactly two keys: "subject" and "body".
- "subject": Keep the thread subject but ensure it starts with 'Re: ' if not already. Current subject: {subject}
- "body": Full email including greeting and sign-off as: {SENDER['name']} | {SENDER['title']} | {SENDER['company']} | {SENDER['website']}
- THE BODY MUST INCLUDE \\n\\n (escaped newlines) BETWEEN EVERY PARAGRAPH. Do NOT output a single flat block of text!
"""

    try:
        response = client.complete(
            messages=[
                {"role": "system", "content": "You are a professional B2B cold email response writer. Output strictly in JSON format without markdown code blocks."},
                {"role": "user", "content": prompt}
            ],
            model="gpt-4o",
            temperature=0.7,
            max_tokens=1000
        )
        
        reply_json_str = response.choices[0].message.content.strip()
        if reply_json_str.startswith("```json"):
            reply_json_str = reply_json_str[7:]
        if reply_json_str.endswith("```"):
            reply_json_str = reply_json_str[:-3]
            
        reply_data = json.loads(reply_json_str)
        
        new_subject = reply_data.get("subject", f"Re: {subject}")
        new_body = reply_data.get("body", "")

        # 3. Store in Review DB
        conn_review = init_review_db()
        c_review = conn_review.cursor()
        
        # Build payload similar to EmailGenerator
        body_json_payload = {
            "body": {
                "generated_content": new_body,
                "subject": new_subject,
                "outreach_data": {
                    "company_name": company_name,
                    "company_email": company_email,
                    "inbox_thread_id": thread_id # Store thread ID so we know it's a reply and can send it in the same thread later
                }
            }
        }

        c_review.execute('''
            INSERT INTO tracking (company_name, company_email, generated_subject, status, body_json)
            VALUES (?, ?, ?, 'pending', ?)
        ''', (company_name, company_email, new_subject, json.dumps(body_json_payload)))
        
        # 4. Update Inbox thread status
        c_inbox.execute("UPDATE inbox_threads SET status = 'drafted' WHERE id = ?", (inbox_id,))
        conn_inbox.commit()
        conn_review.commit()
        
        print(json.dumps({"success": True}))
        
    except Exception as e:
        print(json.dumps({"error": str(e)}))

if __name__ == "__main__":
    try:
        payload = json.loads(sys.stdin.read())
        inbox_id = int(payload.get('inbox_id'))
        draft_reply(inbox_id)
    except Exception as e:
        print(json.dumps({"error": f"Invalid input: {e}"}))
