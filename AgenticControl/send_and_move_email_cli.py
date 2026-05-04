"""
send_and_move_email_cli.py
──────────────────────────────────────────────────────────────────
Atomic CLI: SEND via Gmail first, then MOVE to EmailsSent DB.
If sending fails for any reason, nothing is moved.

Input  (stdin JSON): { "id": <int> }
Output (stdout JSON): { "ok": true/false, "message": "...", "error": "..." }
"""

import json
import sys
import os
import sqlite3

# ── Paths ──────────────────────────────────────────────────────────────────────
REVIEW_DB  = os.path.join(os.environ.get('WORKSPACE_ROOT', '.'), 'Database/EmailsUnderReview/emailsUnderReview.db')
OUTBOX_DB  = os.path.join(os.environ.get('WORKSPACE_ROOT', '.'), 'Database/EmailsSent/email_to_be_sent.db')
DATABASE_JSON = os.path.join(os.environ.get('WORKSPACE_ROOT', '.'), 'backend/database.json')

# Import existing helpers from the same AgenticControl directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from Email_sender import send_email_from_database
from Send_email_db import approve_and_move_email


def send_then_move(email_id: int):
    # ── Step 1: Fetch the row from review DB ──────────────────────────────────
    try:
        conn = sqlite3.connect(REVIEW_DB)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, body_json, timestamp, followup_date, status, "
            "company_name, generated_subject, company_email "
            "FROM tracking WHERE id = ?",
            (email_id,)
        )
        row = cursor.fetchone()
        conn.close()
    except sqlite3.Error as e:
        print(json.dumps({"ok": False, "error": f"DB fetch error: {e}"}))
        return

    if not row:
        print(json.dumps({"ok": False, "error": f"Email ID {email_id} not found in review DB"}))
        return

    db_row = {
        "body_json":     row[1],   # body_json
        "company_email": row[7],   # company_email
        "company_name":  row[5],   # company_name
    }

    # ── Step 2: SEND the email via Gmail ────────────────────────────────────────
    try:
        result = send_email_from_database(db_row, DATABASE_JSON)
        if result is None:
            # send_email_from_database prints the error itself but returns None on failure
            print(json.dumps({"ok": False, "error": "Gmail send failed — check server logs. Email NOT moved."}))
            return
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"Send exception: {e}. Email NOT moved."}))
        return

    # ── Step 3: Only if send succeeded, MOVE the row ────────────────────────────
    moved = approve_and_move_email(email_id)
    if moved:
        print(json.dumps({
            "ok": True,
            "message": f"Email {email_id} sent and moved to EmailsSent. Gmail ID: {result.get('id', '?')}",
        }))
    else:
        # Row was sent but move failed — log it clearly
        print(json.dumps({
            "ok": False,
            "error": f"Email WAS sent (Gmail ID: {result.get('id', '?')}) but DB move FAILED. Check DB manually.",
        }))


# ── CLI entry ──────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    try:
        raw = sys.stdin.read().strip()
        if not raw:
            print(json.dumps({"ok": False, "error": "No input provided"}))
            sys.exit(1)
        payload = json.loads(raw)
        email_id = payload.get('id')
        if email_id is None:
            print(json.dumps({"ok": False, "error": "Missing 'id' in payload"}))
            sys.exit(1)
        send_then_move(int(email_id))
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        sys.exit(1)
