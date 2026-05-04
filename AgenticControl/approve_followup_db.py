import sqlite3
import json
import sys
import os
from datetime import datetime

# ── Paths ─────────────────────────────────────────────────────────────────────
REVIEW_DB   = os.path.join(os.environ.get('WORKSPACE_ROOT', '.'), 'Database/EmailsUnderReview/followups_under_review.db')
SENT_DB     = os.path.join(os.environ.get('WORKSPACE_ROOT', '.'), 'Database/EmailsSent/followups_sent.db')

# ─────────────────────────────────────────────────────────────────────────────
def approve_followup(record_id: int):
    """
    Reads a followup_pending row from followups_under_review.db,
    writes it to followups_sent.db (sent_followups table),
    then removes it from the source DB.
    The Unique_application_id is preserved intact.
    """
    os.makedirs(os.path.dirname(SENT_DB), exist_ok=True)

    try:
        conn_review = sqlite3.connect(REVIEW_DB)
        conn_sent   = sqlite3.connect(SENT_DB)
        conn_review.row_factory = sqlite3.Row

        cur_review = conn_review.cursor()
        cur_sent   = conn_sent.cursor()

        # 1. Ensure destination table exists
        cur_sent.execute('''
            CREATE TABLE IF NOT EXISTS sent_followups (
                id                    INTEGER PRIMARY KEY,
                company_email         TEXT,
                company_name          TEXT,
                generated_subject     TEXT,
                followup_date         DATETIME,
                status                TEXT DEFAULT "approved - queued for sending",
                Unique_application_id TEXT,
                message_id            TEXT,
                body_json             TEXT,
                context               TEXT,
                overall_summary       TEXT,
                approved_at           DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 2. Fetch the follow-up record from under-review DB
        cur_review.execute('SELECT * FROM followups_pending WHERE id = ?', (record_id,))
        row = cur_review.fetchone()

        if not row:
            print(json.dumps({"ok": False, "error": f"Follow-up ID {record_id} not found."}))
            return False

        # 3. Insert into sent_followups
        cur_sent.execute('''
            INSERT INTO sent_followups
            (id, company_email, company_name, generated_subject, followup_date, status,
             Unique_application_id, message_id, body_json, context, overall_summary, approved_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            row['id'],
            row['company_email'],
            row['company_name'],
            row['generated_subject'],
            row['followup_date'],
            'approved - queued for sending',
            row['Unique_application_id'],
            row['message_id'],
            row['body_json'],
            row['context'],
            row['overall_summary'],
            datetime.now().isoformat(sep=' ', timespec='seconds')
        ))

        # 4. Delete from review DB
        cur_review.execute('DELETE FROM followups_pending WHERE id = ?', (record_id,))

        # 5. Commit both
        conn_sent.commit()
        conn_review.commit()

        print(json.dumps({
            "ok": True,
            "message": f"Follow-up {record_id} approved and moved to sent queue.",
            "Unique_application_id": row['Unique_application_id']
        }))
        return True

    except sqlite3.Error as e:
        print(json.dumps({"ok": False, "error": f"Database error: {e}"}))
        if 'conn_sent'   in locals(): conn_sent.rollback()
        if 'conn_review' in locals(): conn_review.rollback()
        return False

    finally:
        if 'conn_review' in locals(): conn_review.close()
        if 'conn_sent'   in locals(): conn_sent.close()


# ── Entry-point ───────────────────────────────────────────────────────────────
if __name__ == '__main__':
    try:
        raw = sys.stdin.read().strip()
        if not raw:
            print(json.dumps({"ok": False, "error": "No input provided"}))
            sys.exit(1)

        payload = json.loads(raw)
        rid = payload.get('id')
        if rid is None:
            print(json.dumps({"ok": False, "error": "No 'id' provided in input"}))
            sys.exit(1)

        approve_followup(int(rid))

    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        sys.exit(1)
