import sqlite3
import json
import os
import time
from datetime import datetime, timedelta
from EmailGenerator import generate_cold_email

# --- CONSTANTS & PATHS ---
BASE_PATH    = os.environ.get('WORKSPACE_ROOT', '.')

# Source: companies imported from .xlsx / .numbers files
DB_EXCEL_DATA = os.path.join(BASE_PATH, 'Database/outreach_data/excel_data.db')

# Destination: review queue shown in the frontend dashboard
DB_TRACKING   = os.path.join(BASE_PATH, 'Database/EmailsUnderReview/emailsUnderReview.db')

# Ensure both directories exist before any DB connection is attempted
os.makedirs(os.path.dirname(DB_EXCEL_DATA), exist_ok=True)
os.makedirs(os.path.dirname(DB_TRACKING),   exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# DATABASE SETUP
# ─────────────────────────────────────────────────────────────────────────────
def init_tracking_db():
    """Create the tracking table if it doesn't exist yet."""
    os.makedirs(os.path.dirname(DB_TRACKING), exist_ok=True)
    with sqlite3.connect(DB_TRACKING) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS tracking (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                body_json        TEXT,
                timestamp        DATETIME DEFAULT CURRENT_TIMESTAMP,
                followup_date    DATETIME,
                status           TEXT DEFAULT 'under review',

                -- core identifiers
                company_name     TEXT,
                company_email    TEXT,

                -- rich outreach fields (carried from excel_data.db)
                website          TEXT,
                address          TEXT,
                total_shipments  TEXT,
                top_suppliers    TEXT,
                hs_codes         TEXT,
                company_description TEXT,
                key_executives   TEXT,
                deep_research_pdf TEXT,

                -- email meta
                generated_subject TEXT,
                date_added       DATETIME
            )
        ''')
        conn.commit()


def dict_factory(cursor, row):
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


# ─────────────────────────────────────────────────────────────────────────────
# DUPLICATE CHECK
# ─────────────────────────────────────────────────────────────────────────────
def already_tracked(company_name: str, company_email: str) -> bool:
    """Return True if this company is already in the tracking DB."""
    with sqlite3.connect(DB_TRACKING) as conn:
        row = conn.execute(
            "SELECT id FROM tracking WHERE company_name = ? AND company_email = ?",
            (company_name, company_email)
        ).fetchone()
    return row is not None


# ─────────────────────────────────────────────────────────────────────────────
# CORE AGENT LOGIC
# ─────────────────────────────────────────────────────────────────────────────
def process_next_company():
    """
    Picks the next unprocessed company from outreach_companies,
    generates a cold email, saves everything to emailsUnderReview.db,
    then marks the source row as 'processed'.
    """

    # 1. Fetch next pending company
    try:
        with sqlite3.connect(DB_EXCEL_DATA) as conn:
            conn.row_factory = dict_factory
            company = conn.execute(
                "SELECT * FROM outreach_companies WHERE status = 'under_review' LIMIT 1"
            ).fetchone()
    except sqlite3.OperationalError:
        # Table doesn't exist yet — Excel_Processor.py hasn't been run
        print(f"[{datetime.now():%H:%M:%S}] Source table not initialised yet. Run Excel_Processor.py first.")
        return False

    if not company:
        print(f"[{datetime.now():%H:%M:%S}] No pending companies found. Sleeping...")
        return False

    company_name  = company.get("company_name", "Unknown")
    company_email = company.get("email", "not updated")

    # 2. Duplicate guard
    if already_tracked(company_name, company_email):
        print(f"[{datetime.now():%H:%M:%S}] Duplicate: '{company_name}' already tracked — marking processed.")
        with sqlite3.connect(DB_EXCEL_DATA) as conn:
            conn.execute(
                "UPDATE outreach_companies SET status = 'processed' WHERE id = ?",
                (company["id"],)
            )
        return True

    # 3. Generate cold email
    print(f"[{datetime.now():%H:%M:%S}] Generating email for '{company_name}'...")
    try:
        raw_email = generate_cold_email(company)   # returns "Subject: ...\n\n<body>"
    except Exception as e:
        print(f"  ❌ Email generation failed: {e}")
        return False

    # Split subject from body
    subject, body = "", raw_email
    if raw_email.startswith("Subject:"):
        lines = raw_email.split("\n\n", 1)
        subject = lines[0].replace("Subject:", "").strip()
        body    = lines[1].strip() if len(lines) > 1 else raw_email

    # 4. Build the JSON blob stored in body_json (keeps backward compat with the frontend)
    final_payload = {
        "body": {
            "generated_content": body,
            "subject": subject,
            "outreach_data": {
                "company_name":        company_name,
                "company_email":       company_email,
                "website":             company.get("website", ""),
                "address":             company.get("address", ""),
                "total_shipments":     company.get("total_shipments", ""),
                "top_suppliers":       company.get("top_suppliers", ""),
                "hs_codes":            company.get("hs_codes", ""),
                "company_description": company.get("company_description", ""),
                "key_executives":      company.get("key_executives", ""),
                "deep_research_pdf":   company.get("deep_research_pdf", ""),
            }
        }
    }
    body_json_str = json.dumps(final_payload)

    # 5. Save to tracking DB
    now          = datetime.now()
    followup_dt  = now + timedelta(days=4)

    with sqlite3.connect(DB_TRACKING) as conn:
        conn.execute('''
            INSERT INTO tracking (
                body_json, timestamp, followup_date, status,
                company_name, company_email,
                website, address, total_shipments, top_suppliers,
                hs_codes, company_description, key_executives, deep_research_pdf,
                generated_subject, date_added
            ) VALUES (
                ?, ?, ?, ?,
                ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?
            )
        ''', (
            body_json_str,
            now.strftime("%Y-%m-%d %H:%M:%S"),
            followup_dt.strftime("%Y-%m-%d %H:%M:%S"),
            'under review',

            company_name,
            company_email,

            company.get("website", ""),
            company.get("address", ""),
            company.get("total_shipments", ""),
            company.get("top_suppliers", ""),
            company.get("hs_codes", ""),
            company.get("company_description", ""),
            company.get("key_executives", ""),
            company.get("deep_research_pdf", ""),

            subject,
            now.strftime("%Y-%m-%d %H:%M:%S"),
        ))
        conn.commit()

    # 6. Mark source row as processed
    with sqlite3.connect(DB_EXCEL_DATA) as conn:
        conn.execute(
            "UPDATE outreach_companies SET status = 'processed' WHERE id = ?",
            (company["id"],)
        )
        conn.commit()

    print(f"  ✅ Saved to tracking DB — '{company_name}' | email: {company_email}")
    print(f"     Subject: {subject}")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# AGENT DAEMON LOOP
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  Textile Outreach Agent — starting single run")
    print("=" * 60)
    init_tracking_db()
    try:
        result = process_next_company()
        if not result:
            print("Nothing to process.")
    except Exception as e:
        print(f"[{datetime.now():%H:%M:%S}] Agent error: {e}")
        raise