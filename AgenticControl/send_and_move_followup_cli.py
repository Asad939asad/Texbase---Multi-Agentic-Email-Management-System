"""
send_and_move_followup_cli.py
──────────────────────────────────────────────────────────────────
Atomic CLI: SEND a follow-up email via Gmail, then MOVE it from
followups_under_review.db → followups_sent.db.
If sending fails, nothing is moved.

Input  (stdin JSON): { "id": <int> }
Output (stdout JSON): { "ok": true/false, "message": "...", "error": "..." }
"""

import json
import sys
import os
import sqlite3

# ── Paths ──────────────────────────────────────────────────────────────────────
REVIEW_DB     = os.path.join(os.environ.get('WORKSPACE_ROOT', '.'), 'Database/EmailsUnderReview/followups_under_review.db')
DATABASE_JSON = os.path.join(os.environ.get('WORKSPACE_ROOT', '.'), 'backend/database.json')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from Email_sender import send_email_from_database
from approve_followup_db import approve_followup


def send_then_move_followup(record_id: int):
    # ── Step 1: Fetch the row from followups_under_review ─────────────────────
    try:
        conn = sqlite3.connect(REVIEW_DB)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM followups_pending WHERE id = ?', (record_id,))
        row = cursor.fetchone()
        conn.close()
    except sqlite3.Error as e:
        print(json.dumps({"ok": False, "error": f"DB fetch error: {e}"}))
        return

    if not row:
        print(json.dumps({"ok": False, "error": f"Follow-up ID {record_id} not found in review DB"}))
        return

    # Build the db_row dict that Email_sender expects
    db_row = {
        "body_json":     row["body_json"],
        "company_email": row["company_email"],
        "company_name":  row["company_name"],
    }

    # ── Step 2: SEND via Gmail ─────────────────────────────────────────────────
    try:
        # We pass row["Unique_application_id"] to preserve the thread in the master DB
        result = send_email_from_database(db_row, DATABASE_JSON, existing_unique_id=row["Unique_application_id"])
        if result is None:
            print(json.dumps({"ok": False, "error": "Gmail send failed — check server logs. Follow-up NOT moved."}))
            return
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"Send exception: {e}. Follow-up NOT moved."}))
        return

    # ── Step 3: MOVE only after successful send ────────────────────────────────
    moved = approve_followup(record_id)
    if moved:
        print(json.dumps({
            "ok": True,
            "message": f"Follow-up {record_id} sent and moved to EmailsSent. Gmail ID: {result.get('id', '?')}",
            "Unique_application_id": row["Unique_application_id"],
        }))
    else:
        print(json.dumps({
            "ok": False,
            "error": f"Follow-up WAS sent (Gmail ID: {result.get('id', '?')}) but DB move FAILED. Check DB manually.",
        }))


# ── CLI entry ──────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    try:
        raw = sys.stdin.read().strip()
        if not raw:
            print(json.dumps({"ok": False, "error": "No input provided"}))
            sys.exit(1)
        payload = json.loads(raw)
        record_id = payload.get('id')
        if record_id is None:
            print(json.dumps({"ok": False, "error": "Missing 'id' in payload"}))
            sys.exit(1)
        send_then_move_followup(int(record_id))
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        sys.exit(1)
