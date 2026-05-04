"""
update_client_email.py
──────────────────────
Utility to update email content and metadata across different outreach databases.

Usage:
    python3 update_client_email.py  (expects JSON via stdin)
"""

import sqlite3
import json
import sys
import os

DB_REVIEW = os.path.join(os.environ.get('WORKSPACE_ROOT', os.path.join(os.environ.get('WORKSPACE_ROOT', '.'), 'Database/EmailsUnderReview/emailsUnderReview.db')))
DB_READY  = os.path.join(os.environ.get('WORKSPACE_ROOT', os.path.join(os.environ.get('WORKSPACE_ROOT', '.'), 'Database/EmailsSent/email_to_be_sent.db')))

def update_email_content(db_id: int, new_body: str = None, new_subject: str = None, db_path: str = DB_REVIEW) -> dict:
    table = "ready_emails" if "email_to_be_sent" in db_path else "tracking"
    
    if not os.path.exists(db_path):
        return {"ok": False, "error": f"Database not found: {db_path}"}

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(f"SELECT body_json FROM {table} WHERE id = ?", (db_id,)).fetchone()
        if not row:
            return {"ok": False, "error": f"Record {db_id} not found in {table}"}

        try:
            payload = json.loads(row['body_json'])
        except:
            payload = {"body": {}}
        
        body_block = payload.setdefault("body", {})
        if new_body is not None:
            body_block["generated_content"] = new_body
        if new_subject is not None:
            body_block["subject"] = new_subject
            conn.execute(f"UPDATE {table} SET generated_subject = ? WHERE id = ?", (new_subject, db_id))

        conn.execute(f"UPDATE {table} SET body_json = ? WHERE id = ?", (json.dumps(payload), db_id))
        conn.commit()
    
    return {"ok": True}

def update_flat_field(db_id: int, field: str, value: str, db_path: str = DB_REVIEW) -> dict:
    table = "ready_emails" if "email_to_be_sent" in db_path else "tracking"
    
    ALLOWED = {
        "company_email", "company_name", "website", "address", "status",
        "total_shipments", "top_suppliers", "hs_codes", "key_executives",
        "generated_subject", "followup_date", "company_description",
    }
    if field not in ALLOWED:
        return {"ok": False, "error": f"Field '{field}' not allowed"}

    if not os.path.exists(db_path):
        return {"ok": False, "error": f"Database not found: {db_path}"}

    with sqlite3.connect(db_path) as conn:
        changed = conn.execute(f"UPDATE {table} SET {field} = ? WHERE id = ?", (value, db_id)).rowcount
        conn.commit()
    
    if changed == 0:
        return {"ok": False, "error": f"Record {db_id} not found in {table}"}
    
    return {"ok": True}

def _cli_mode():
    try:
        input_data = sys.stdin.read().strip()
        if not input_data:
            # If no stdin, maybe it's being run interactively?
            return
        payload = json.loads(input_data)
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"Invalid JSON: {e}"}))
        sys.exit(1)

    db_id = payload.get("id")
    db_type = payload.get("dbType", "review")
    db_path = DB_READY if db_type == "ready" else DB_REVIEW

    if not db_id:
        print(json.dumps({"ok": False, "error": "Missing id"}))
        sys.exit(1)

    if "new_body" in payload or "new_subject" in payload:
        result = update_email_content(
            db_id, 
            new_body=payload.get("new_body"), 
            new_subject=payload.get("new_subject"),
            db_path=db_path
        )
    elif "field" in payload and "value" in payload:
        result = update_flat_field(db_id, payload["field"], payload["value"], db_path=db_path)
    else:
        result = {"ok": False, "error": "Invalid action"}

    print(json.dumps(result))

if __name__ == "__main__":
    _cli_mode()
