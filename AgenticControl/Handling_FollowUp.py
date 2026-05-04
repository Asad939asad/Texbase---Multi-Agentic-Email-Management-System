# Button is pressed or 24 hours have passed since the email was sent.
# Then send a follow-up email. 
# An email copy will be made in the followup database
# and unique identifier to maintain tracing in the 
# new database once the user has approved it will be sen
# and will again come in the followup database with same unique identifier
# and maximum allowed feed backs are 3 on which further work will be done
#
#
#-------------------------------------------------------------------------------------------
"""
followupTracker(id): //you will get the email from Database/FollowUps/sent_emails.db using 'id'
    make a separate database for such cases in the Database/EmailsUnderReview
    and also add a column for context which will come along from the database
    "                company_email TEXT,
                role TEXT,
                date_applied DATETIME,
                followup_date DATETIME,
                status TEXT,
                Unique_application_id TEXT,
                message_id TEXT,
                body_json TEXT
            )"
    in the new database there will be a new column for overall summary and write it in bullet points as
    there might be existing bullet points so simple add an extra so basically 
    context contains all the summaries of past emails which will. be used to generate a followup email 
    and rest everything same as body json will contain new email generated as a followup and 
    will be saved in the database
    so followups are handled properly and no problem occurs 
    the column in new database:"overall_summary"
    and remember that all other informations should be carried along especially the 
    unique_application_id 

    Use the github token to generate new email
    "def generate_application_body(company_data: dict, user_data: dict) -> str:
    
    if not GITHUB_TOKEN:
        print("Error: GITHUB_TOKEN not found in environment variables.")
        return "{}"

    # Initialize the Azure/GitHub inference client
    try:
        endpoint = "https://models.github.ai/inference"
        client = ChatCompletionsClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(GITHUB_TOKEN),
        )
        print("Client initialized successfully")
    except Exception as e:
        print(f"Error initializing client: {e}")
        return "{}""

        use "def call_llm(system_prompt, user_query):
    payload = {
        "system_prompt": system_prompt,
        "query": user_query,
        "max_new_tokens": 1000
    }
    response = requests.post(LLM_URL, json=payload)
    if response.status_code == 200:
        return response.json()["response"]
    raise Exception(f"LLM Error: {response.text}")"

    to summarize the emails



"""
import os
import sqlite3
import json
import requests
from datetime import datetime

# Import the Azure/GitHub inference client
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv

# ==========================================
# CONFIGURATION & LLM HELPERS
# ==========================================
# It is best practice to set this in your terminal (export GITHUB_TOKEN="..."), 
# but I have included your fallback token here for easy testing.
load_dotenv(dotenv_path=os.path.join(os.environ.get('WORKSPACE_ROOT', '.'), 'backend/.env'))
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
LLM_URL = "http://localhost:8003/generate" 

def call_llm(system_prompt: str, user_query: str) -> str:
    """
    Calls your custom local LLM endpoint to summarize the previous email.
    """
    payload = {
        "system_prompt": system_prompt,
        "query": user_query,
        "max_new_tokens": 1000
    }
    try:
        response = requests.post(LLM_URL, json=payload)
        response.raise_for_status() # Raises an error for bad HTTP status codes
        return response.json().get("response", "No response generated.")
    except Exception as e:
        raise Exception(f"Local LLM Error: {e}")

def generate_application_body(company_email: str, company_name: str, context: str) -> str:
    """
    Uses GitHub Models (gpt-4o) to generate the new follow-up email.
    """
    if not GITHUB_TOKEN:
        print("❌ Error: GITHUB_TOKEN not found.")
        return "{}"

    try:
        endpoint = "https://models.github.ai/inference"
        client = ChatCompletionsClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(GITHUB_TOKEN),
        )
        print("🤖 GitHub Client initialized successfully.")
        
        system_prompt = "You are an AI assistant helping a textile sales manager write professional follow-up emails for B2B outreach."
        user_prompt = f"""
        Company: {company_name}
        Company Email: {company_email}
        Past Context / Summaries:
        {context}
        
        Write a polite, concise follow-up email asking if they've had a chance to review our previous proposal. 
        Format the output STRICTLY as valid JSON. Do not include markdown formatting like ```json.
        Structure:
        {{
          "body": {{
            "generated_content": "Subject: Following up on our partnership proposal - [Company Name]<br><br>Hi Team,<br><br>..."
          }}
        }}
        """

        response = client.complete(
            messages=[
                SystemMessage(content=system_prompt),
                UserMessage(content=user_prompt)
            ],
            model="gpt-4o", 
            temperature=0.7,
            max_tokens=1000
        )
        
        # Clean up any markdown blocks if the LLM adds them
        content = response.choices[0].message.content.strip()
        if content.startswith("```json"):
            content = content[7:-3].strip()
        elif content.startswith("```"):
            content = content[3:-3].strip()
            
        return content

    except Exception as e:
        print(f"❌ Error generating follow-up email: {e}")
        return "{}"

# ==========================================
# MAIN TRACKER LOGIC
# ==========================================
def followupTracker(record_id):
    """
    Extracts the old email, summarizes it, generates a new follow-up email, 
    and saves the entire package to the EmailsUnderReview database.
    """
    source_db_path = os.path.join(os.environ.get('WORKSPACE_ROOT', '.'), 'Database/FollowUps/sent_emails.db')
    dest_dir = os.path.join(os.environ.get('WORKSPACE_ROOT', '.'), 'Database/EmailsUnderReview')
    os.makedirs(dest_dir, exist_ok=True)
    dest_db_path = os.path.join(dest_dir, 'followups_under_review.db')

    # 1. FETCH FROM SOURCE DATABASE
    try:
        source_conn = sqlite3.connect(source_db_path)
        source_conn.row_factory = sqlite3.Row
        cursor = source_conn.cursor()

        # Works with either the integer ID or the 20-digit string ID
        cursor.execute("SELECT * FROM sent_applications WHERE id = ? OR Unique_application_id = ?", (record_id, str(record_id)))
        record = cursor.fetchone()

        if not record:
            print(f"❌ No record found in sent_emails.db with ID: {record_id}")
            return

        company_email = record["company_email"]
        company_name = record["company_name"]
        generated_subject = record["generated_subject"]
        followup_date = record["followup_date"]
        unique_application_id = record["Unique_application_id"]
        message_id = record["message_id"]
        old_body_json_str = record["body_json"]

    except sqlite3.Error as e:
        print(f"❌ Source Database error: {e}")
        return
    finally:
        if 'source_conn' in locals() and source_conn:
            source_conn.close()

    # 2. EXTRACT OLD EMAIL TEXT & SUMMARIZE IT
    try:
        old_data = json.loads(old_body_json_str)
        # Dig into the JSON to get just the actual email text
        old_email_text = old_data.get("body", {}).get("generated_content", "No content found.")
    except Exception:
        # Fallback if the database string isn't perfectly formatted JSON
        old_email_text = old_body_json_str

    try:
        print("📝 Summarizing previous email via Local LLM...")
        summary_sys_prompt = "You summarize emails concisely into exactly one short sentence."
        summary_query = f"Summarize this email:\n{old_email_text}"
        new_summary_text = call_llm(summary_sys_prompt, summary_query)
        
        current_date = datetime.now().strftime('%Y-%m-%d')
        new_bullet = f"• {current_date}: {new_summary_text.strip()}"
        print(f"✅ Summary generated: {new_bullet}")
    except Exception as e:
        print(f"⚠️ Summarization skipped or failed: {e}")
        new_bullet = f"• {datetime.now().strftime('%Y-%m-%d')}: Follow-up initiated for {company_name}."

    # 3. SAVE/UPDATE DESTINATION DATABASE
    try:
        dest_conn = sqlite3.connect(dest_db_path)
        dest_cursor = dest_conn.cursor()

        dest_cursor.execute('''
            CREATE TABLE IF NOT EXISTS followups_pending (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_email TEXT,
                company_name TEXT,
                generated_subject TEXT,
                followup_date DATETIME,
                status TEXT,
                Unique_application_id TEXT,
                message_id TEXT,
                body_json TEXT,
                context TEXT,
                overall_summary TEXT
            )
        ''')

        # Check if this application thread already exists in the UnderReview DB
        dest_cursor.execute("SELECT overall_summary, context FROM followups_pending WHERE Unique_application_id = ?", (unique_application_id,))
        existing_record = dest_cursor.fetchone()

        if existing_record:
            existing_summary = existing_record[0] if existing_record[0] else ""
            overall_summary = f"{existing_summary}\n{new_bullet}"
            context = existing_record[1] if existing_record[1] else f"Company: {company_name} ({company_email})"
            is_update = True
        else:
            overall_summary = new_bullet
            context = f"Company: {company_name} ({company_email})\nInitial Outreach: {generated_subject}"
            is_update = False

        # Build the complete context string to feed to the GitHub Model
        full_context_for_llm = f"{context}\n\nEmail History:\n{overall_summary}"

        # 4. GENERATE THE NEW FOLLOW-UP EMAIL JSON
        print("⚙️ Generating new follow-up email draft via GitHub Models...")
        new_email_json_str = generate_application_body(company_email, company_name, full_context_for_llm)

        status = "Draft Generated - Pending Review"

        # 5. COMMIT TO DESTINATION DB
        if is_update:
            dest_cursor.execute('''
                UPDATE followups_pending
                SET status = ?, body_json = ?, overall_summary = ?, context = ?
                WHERE Unique_application_id = ?
            ''', (status, new_email_json_str, overall_summary, full_context_for_llm, unique_application_id))
            print(f"✅ Updated existing tracker and saved new draft. (ID: {unique_application_id})")
        else:
            dest_cursor.execute('''
                INSERT INTO followups_pending
                (company_email, company_name, generated_subject, followup_date, status, Unique_application_id, message_id, body_json, context, overall_summary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                company_email, company_name, generated_subject, followup_date, status, unique_application_id, message_id, new_email_json_str, full_context_for_llm, overall_summary
            ))
            print(f"✅ Created new tracker and saved first follow-up draft. (ID: {unique_application_id})")

        dest_conn.commit()

    except sqlite3.Error as e:
        print(f"❌ Destination Database error: {e}")
    finally:
        if 'dest_conn' in locals() and dest_conn:
            dest_conn.close()
            print("Done! 🎉")

# ==========================================
# CLI ENTRY POINT
# ==========================================
if __name__ == "__main__":
    import sys
    try:
        raw_input = sys.stdin.read().strip()
        if not raw_input:
            print(json.dumps({"ok": False, "error": "No input provided"}))
            sys.exit(1)
            
        payload = json.loads(raw_input)
        record_id = payload.get("id")
        
        if not record_id:
            print(json.dumps({"ok": False, "error": "Missing 'id' in input"}))
            sys.exit(1)
            
        # Run the tracker logic
        followupTracker(record_id)
        
        # Output success for the server to parse
        print(json.dumps({"ok": True}))
        
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        sys.exit(1)