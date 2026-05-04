"""
OutreachAgent.py
────────────────
Background worker that polls the "Ready to Send" (Outbox) databases and triggers
the actual Gmail sending process. Once sent, records are cleared from the outbox
and persist in the master "Follow-up Journey" database.
"""

import time
import sqlite3
import os
import json
import sys
from datetime import datetime

# ── Paths ─────────────────────────────────────────────────────────────────────
COLD_OUTBOX_DB = os.path.join(os.environ.get('WORKSPACE_ROOT', '.'), 'Database/EmailsSent/email_to_be_sent.db')
FOLLOWUP_OUTBOX_DB = os.path.join(os.environ.get('WORKSPACE_ROOT', '.'), 'Database/EmailsSent/followups_sent.db')
DATABASE_JSON = os.path.join(os.environ.get('WORKSPACE_ROOT', '.'), 'backend/database.json')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from Email_sender import send_email_from_database

def process_cold_outbox():
    if not os.path.exists(COLD_OUTBOX_DB): return
    
    conn = sqlite3.connect(COLD_OUTBOX_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Fetch records that haven't been processed yet
        # (We delete them after success, but we skip 'sent' status just in case)
        cursor.execute("SELECT * FROM ready_emails WHERE company_email != 'not updated' AND status != 'sent'")
        rows = cursor.fetchall()
        
        for row in rows:
            print(f"🚀 [OutreachAgent] Processing cold email to {row['company_email']}...")
            
            # Prepare row for Email_sender
            db_row = {
                "body_json": row["body_json"],
                "company_email": row["company_email"],
                "company_name": row["company_name"],
                "generated_subject": row["generated_subject"]
            }
            
            try:
                # Send the email
                result = send_email_from_database(db_row, DATABASE_JSON)
                
                if result and result.get('id'):
                    # Success! Remove from outbox
                    print(f"✅ [OutreachAgent] Sent successfully (ID: {result['id']}). Clearing from outbox.")
                    cursor.execute("DELETE FROM ready_emails WHERE id = ?", (row['id'],))
                    conn.commit()
                else:
                    print(f"⚠️ [OutreachAgent] Send failed for {row['company_email']}. Will retry next loop.")
            except Exception as e:
                print(f"❌ [OutreachAgent] Error sending cold email: {e}")
                
    except sqlite3.Error as e:
        print(f"❌ [OutreachAgent] Cold outbox DB error: {e}")
    finally:
        conn.close()

def process_followup_outbox():
    if not os.path.exists(FOLLOWUP_OUTBOX_DB): return
    
    conn = sqlite3.connect(FOLLOWUP_OUTBOX_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT * FROM sent_followups WHERE company_email != 'not updated'")
        rows = cursor.fetchall()
        
        for row in rows:
            print(f"🚀 [OutreachAgent] Processing follow-up to {row['company_email']} (ID: {row['Unique_application_id']})...")
            
            db_row = {
                "body_json": row["body_json"],
                "company_email": row["company_email"],
                "company_name": row["company_name"],
                "generated_subject": row["generated_subject"]
            }
            
            try:
                # Send the email and preserve the unique ID thread
                result = send_email_from_database(db_row, DATABASE_JSON, existing_unique_id=row["Unique_application_id"])
                
                if result and result.get('id'):
                    print(f"✅ [OutreachAgent] Follow-up sent. Clearing from outbox.")
                    cursor.execute("DELETE FROM sent_followups WHERE id = ?", (row['id'],))
                    conn.commit()
                else:
                    print(f"⚠️ [OutreachAgent] Follow-up send failed. Will retry.")
            except Exception as e:
                print(f"❌ [OutreachAgent] Error sending follow-up: {e}")
                
    except sqlite3.Error as e:
        print(f"❌ [OutreachAgent] Follow-up outbox DB error: {e}")
    finally:
        conn.close()

def run_agent():
    print("🔥 Outreach Background Agent Started.")
    print(f"Monitoring Cold Outbox: {os.path.basename(COLD_OUTBOX_DB)}")
    print(f"Monitoring Follow-up Outbox: {os.path.basename(FOLLOWUP_OUTBOX_DB)}")
    
    while True:
        try:
            # 1. Process Cold Outreach
            process_cold_outbox()
            
            # 2. Process Follow-ups
            process_followup_outbox()
            
        except Exception as e:
            print(f"‼️ [OutreachAgent] Fatal loop error: {e}")
        
        # Poll every 30 seconds
        time.sleep(30)

if __name__ == "__main__":
    run_agent()
