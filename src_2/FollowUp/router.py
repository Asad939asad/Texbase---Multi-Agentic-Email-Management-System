#!/usr/bin/python3
"""
router.py — FollowUp Agent
============================
Two-step LLM routing pipeline:

  Step 1 — Intent & Routing:
    Gemini reads the incoming email + full schema catalog of all 4 databases
    → Returns JSON routing plan: which DBs/tables to query, intent, reply tone

  Step 2 — Execute + Draft:
    Execute the SQL queries from routing plan
    Assemble results as context
    Second Gemini call → draft reply email
    Save draft to sent table

Public API
----------
  route_email(email_text, sender, subject, received_at) -> dict
----------
"""

from __future__ import annotations
import json
import os
import re
import sys
import sqlite3
import datetime
import hashlib

sys.path.insert(0, os.path.dirname(__file__))
from db_setup import get_conn, DB_PATH

from google import genai
from google.genai import types

GEMINI_API_KEY = "AIzaSyCjpq029SbLWQxyqUhElxCWCBlZHoTqsgc"
client         = genai.Client(api_key=GEMINI_API_KEY)

# ── Linked database paths ─────────────────────────────────────────────────────
LINKED_DBS = {
    'po_database.db')):        "/Volumes/ssd2/TEXBASE/src/PO:Quotation/po_database.db')),
    'outreach_tracker.db')):   '/Volumes/ssd2/TEXBASE/src/ColdEmail/outreach_tracker.db')),
    'cashflow.db')):           '/Volumes/ssd2/TEXBASE/src/CashFlowCareTaker/cashflow.db')),
    'email_inbox.db')):        DB_PATH,
}

def _get_dynamic_db_catalog() -> str:
    """Dynamically build the catalog for po_database.db, but use static descriptions for the rest."""
    catalog_lines = ["━━━ TEXBASE DATABASE CATALOG ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"]
    
    # DB 1: Dynamic Purchase Orders
    db1_path = LINKED_DBS.get('po_database.db')))
    catalog_lines.append("\nDB 1: po_database.db  (Purchase Orders — what clients ordered from us)")
    if db1_path and os.path.exists(db1_path):
        try:
            conn = sqlite3.connect(db1_path)
            tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()
            for (table_name,) in tables:
                cols = conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()
                col_names = [c[1] for c in cols]
                catalog_lines.append(f"  Table: {table_name}")
                catalog_lines.append(f"    Columns: {', '.join(col_names)}")
            conn.close()
        except Exception as e:
            catalog_lines.append(f"  [Error reading schema: {e}]")
    else:
        catalog_lines.append("  [File not found]")
        
    catalog_lines.append("  → Query when email is about: orders, PO numbers, delivery dates, items")

    # DB 2, 3, 4: Static Schemas with usage hints
    catalog_lines.append("""
DB 2: outreach_tracker.db  (Cold Email CRM — prospective clients)
  Table: outreach_companies
    Columns: id, company_id, company_name, website, company_profile, deep_research_summary, run_date
  Table: outreach_contacts
    Columns: id, company_id, company_name, contact_name, contact_title, contact_email, contacted, status
  → Query when email is about: new vendor/buyer inquiry, sourcing partnership, cold-email reply

DB 3: cashflow.db  (Cash Flow — financial transactions)
  Table: intakes  (money IN)
    Columns: id, description, amount_usd, amount_pkr, date, counterparty
  Table: outtakes  (money OUT)
    Columns: id, description, amount_usd, amount_pkr, date, counterparty
  → Query when email is about: payment confirmation, invoice amount, overdue balance, receipt

DB 4: email_inbox.db  (Email History — our inbox & sent)
  Table: inbox
    Columns: id, sender, subject, body, received_at, thread_id, status
  Table: sent
    Columns: id, inbox_id, to_address, subject, body, original_email_body, sent_at
  → **ALWAYS query** to retrieve thread history and prior replies""")

    catalog_lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(catalog_lines)


SENDER_PROFILE = """
We are: Arooj Enterprises | Premium Garment Manufacturing & Export
Established: 1993 | Certifications: ISO 14001, SEDEX, OEKO-TEX
Capacity: 1M units/month | Contact: Asad Irfan, Senior Marketing Manager
Website: www.texbase.com
"""


# ══════════════════════════════════════════════════════════════════════════════
#  GEMINI HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _gemini(prompt: str, temperature: float = 0.1) -> str:
    try:
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(temperature=temperature),
        )
        return resp.text.strip()
    except Exception as e:
        print(f"  [Gemini] Error: {e}")
        return ""


def _parse_json(text: str) -> dict | list:
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"```\s*$", "", text, flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


# ══════════════════════════════════════════════════════════════════════════════
#  STEP 1 — ROUTING DECISION
# ══════════════════════════════════════════════════════════════════════════════

def step1_routing_decision(email_text: str, sender: str, subject: str,
                           thread_history: list) -> dict:
    """
    Ask Gemini to classify the email intent and produce a routing plan.
    Returns structured JSON routing plan.
    """
    history_text = ""
    if thread_history:
        history_text = "\n\nTHREAD HISTORY (previous emails in this conversation):\n"
        for h in thread_history[-3:]:   # last 3 emails max
            history_text += f"  [{h['received_at']}] From: {h['sender']}\n  {h['body'][:300]}\n\n"

    prompt = f"""You are the intelligent routing engine for Arooj Enterprises' email management system.

{SENDER_PROFILE}

{_get_dynamic_db_catalog()}
{history_text}

INCOMING EMAIL:
  From    : {sender}
  Subject : {subject}
  Body    :
{email_text}

YOUR TASK:
1. Classify the intent of this email.
2. Select ONLY the databases that are logically relevant to the sender or the subject matter (e.g., do NOT query po_database.db if it's a cold inquiry with no order history).
3. Within those RELEVANT databases, generate AS MANY QUERIES AS POSSIBLE using flexible matching to avoid missing data.
   - For example, if trying to find a company, query by full name, by domain name, and by sender email.
   - Use flexible matching (e.g., `LIKE '%word%'`) rather than strict equality (`=`).
   - If querying amounts, query for amounts near the mentioned number.
4. For each database, specify the exact SQL WHERE clause to use.
5. Note: email_inbox.db must ALWAYS be included to check thread history.

Return ONLY a raw JSON object with this exact structure:
{{
  "intent": "one of: payment_inquiry | order_status | sourcing_inquiry | cold_reply | complaint | general | unknown",
  "summary": "one-line summary of what the sender is asking",
  "tables_to_query": [
    {{
      "db": 'cashflow.db')),
      "table": "intakes",
      "reason": "Check if we received payment from this sender"
    }}
  ],
  "suggested_reply_tone": "professional and warm | firm reminder | welcoming | apologetic",
  "priority": "high | medium | low",
  "requires_human_review": true or false
}}

Do not return anything else."""

    print("\n[Router Step 1] Gemini classifying intent and generating routing plan…")
    raw   = _gemini(prompt, temperature=0.1)
    plan  = _parse_json(raw)
    if plan:
        print(f"  Intent   : {plan.get('intent')}")
        print(f"  Summary  : {plan.get('summary')}")
        print(f"  Tables   : {[q.get('table') for q in plan.get('tables_to_query', [])]}")
        print(f"  Priority : {plan.get('priority')}")
    else:
        print("  [WARN] Could not parse routing plan JSON.")
    return plan


# ══════════════════════════════════════════════════════════════════════════════
#  STEP 1b — GENERATE EXACT SQL BASED ON SCHEMA
# ══════════════════════════════════════════════════════════════════════════════

def step1b_generate_sql(email_text: str, sender: str, subject: str, routing_plan: dict) -> dict:
    """Take the selected tables, fetch exact schema, and prompt Gemini for robust SQL Queries."""
    schema_context = []
    for item in routing_plan.get("tables_to_query", []):
        db_name = item.get("db")
        table_name = item.get("table")
        db_path = LINKED_DBS.get(db_name)
        if db_path and os.path.exists(db_path):
            try:
                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
                cols = conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()
                col_info = [f"{c['name']} ({c['type']})" for c in cols]
                sample_row = conn.execute(f"SELECT * FROM `{table_name}` LIMIT 1").fetchone()
                sample_str = dict(sample_row) if sample_row else "No rows yet"
                schema_context.append(f"DB: {db_name} | Table: {table_name}\\nColumns: {', '.join(col_info)}\\nSample Row: {sample_str}\\n")
                conn.close()
            except Exception as e:
                pass

    if not schema_context:
        routing_plan["databases_to_query"] = []
        return routing_plan

    prompt = f"""You are the database querying expert for Arooj Enterprises.
EMAIL:
From: {sender}
Subject: {subject}
Body: {email_text}

INTENT: {routing_plan.get('intent')}
SUMMARY: {routing_plan.get('summary')}

EXACT TABLE SCHEMAS OBTAINED FROM LIVE DATABASE:
{"".join(schema_context)}

TASK:
Write the exact SQL WHERE clauses to retrieve the most relevant records for this email.
Generate AS MANY QUERIES AS POSSIBLE using flexible matching to avoid missing data.
- For example, if trying to find a company, query by full name, by domain name, and by sender email.
- Use flexible matching (e.g., `LOWER(col) LIKE '%word%'`) rather than strict equality (`=`).
- If querying amounts, query for amounts near the mentioned number.

Return ONLY a JSON array of query objects formatting exactly like:
[
  {{
    "db": 'cashflow.db')),
    "table": "intakes",
    "sql": "SELECT * FROM `intakes` WHERE LOWER(counterparty) LIKE '%...%' LIMIT 5",
    "reason": "search by sender email domain"
  }}
]
"""
    print("\\n[Router Step 1b] Gemini generating precise SQL queries based on exact schema…")
    raw = _gemini(prompt, temperature=0.1)
    queries = _parse_json(raw)
    if isinstance(queries, list):
        routing_plan["databases_to_query"] = queries
    else:
        routing_plan["databases_to_query"] = []
        
    return routing_plan


# ══════════════════════════════════════════════════════════════════════════════
#  STEP 1b — GENERATE EXACT SQL BASED ON SCHEMA
# ══════════════════════════════════════════════════════════════════════════════

def step1b_generate_sql(email_text: str, sender: str, subject: str, routing_plan: dict) -> dict:
    """Take the selected tables, fetch exact schema, and prompt Gemini for robust SQL Queries."""
    schema_context = []
    for item in routing_plan.get("tables_to_query", []):
        db_name = item.get("db")
        table_name = item.get("table")
        db_path = LINKED_DBS.get(db_name)
        if db_path and os.path.exists(db_path):
            try:
                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
                cols = conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()
                col_info = [f"{c['name']} ({c['type']})" for c in cols]
                sample_row = conn.execute(f"SELECT * FROM `{table_name}` LIMIT 1").fetchone()
                sample_str = dict(sample_row) if sample_row else "No rows yet"
                schema_context.append(f"DB: {db_name} | Table: {table_name}\\nColumns: {', '.join(col_info)}\\nSample Row: {sample_str}\\n")
                conn.close()
            except Exception as e:
                pass

    if not schema_context:
        routing_plan["databases_to_query"] = []
        return routing_plan

    prompt = f"""You are the database querying expert for Arooj Enterprises.
EMAIL:
From: {sender}
Subject: {subject}
Body: {email_text}

INTENT: {routing_plan.get('intent')}
SUMMARY: {routing_plan.get('summary')}

EXACT TABLE SCHEMAS OBTAINED FROM LIVE DATABASE:
{"".join(schema_context)}

TASK:
Write the exact SQL WHERE clauses to retrieve the most relevant records for this email.
Generate AS MANY QUERIES AS POSSIBLE using flexible matching to avoid missing data.
- For example, if trying to find a company, query by full name, by domain name, and by sender email.
- Use flexible matching (e.g., `LOWER(col) LIKE '%word%'`) rather than strict equality (`=`).
- If querying amounts, query for amounts near the mentioned number.

Return ONLY a JSON array of query objects formatting exactly like:
[
  {{
    "db": 'cashflow.db')),
    "table": "intakes",
    "sql": "SELECT * FROM `intakes` WHERE LOWER(counterparty) LIKE '%...%' LIMIT 5",
    "reason": "search by sender email domain"
  }}
]
"""
    print("\\n[Router Step 1b] Gemini generating precise SQL queries based on exact schema…")
    raw = _gemini(prompt, temperature=0.1)
    queries = _parse_json(raw)
    if isinstance(queries, list):
        routing_plan["databases_to_query"] = queries
    else:
        routing_plan["databases_to_query"] = []
        
    return routing_plan


# ══════════════════════════════════════════════════════════════════════════════
#  STEP 2 — EXECUTE QUERIES + DRAFT REPLY
# ══════════════════════════════════════════════════════════════════════════════

def _execute_query(db_name: str, sql: str) -> list[dict]:
    """Run one SQL query against the specified DB. Returns list of row dicts."""
    db_path = LINKED_DBS.get(db_name)
    if not db_path or not os.path.exists(db_path):
        print(f"  [SQL] DB not found: {db_name}")
        return []
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"  [SQL] Error on {db_name}: {e}")
        return []


def step2_execute_and_draft(email_text: str, sender: str, subject: str,
                             routing_plan: dict) -> str:
    """
    Execute SQL queries from routing plan, assemble results, draft reply.
    Returns the drafted reply email body.
    """
    # ── Execute all queries ───────────────────────────────────────────────
    context_parts = []
    for q in routing_plan.get("databases_to_query", []):
        db    = q.get("db", "")
        sql   = q.get("sql", "")
        reason = q.get("reason", "")
        if not sql:
            continue
        print(f"  [SQL] Querying {db}: {sql[:80]}…")
        rows = _execute_query(db, sql)
        if rows:
            context_parts.append(
                f"\n--- {db} | {q.get('table','')} ({reason}) ---\n"
                + json.dumps(rows[:10], indent=2, default=str)
            )
        else:
            context_parts.append(
                f"\n--- {db} | {q.get('table','')} ({reason}) ---\n  (no records found)"
            )

    context = "\n".join(context_parts) or "  (No database records retrieved)"

    # ── Draft reply ───────────────────────────────────────────────────────
    tone = routing_plan.get("suggested_reply_tone", "professional and warm")
    intent = routing_plan.get("intent", "general")
    summary = routing_plan.get("summary", "")

    draft_prompt = f"""You are composing a professional email reply on behalf of Arooj Enterprises.

{SENDER_PROFILE}

ORIGINAL EMAIL:
  From    : {sender}
  Subject : {subject}
  Body    :
{email_text}

EMAIL INTENT: {intent}
SUMMARY: {summary}
REPLY TONE: {tone}

RELEVANT BUSINESS DATA RETRIEVED FROM OUR DATABASES:
{context}

TASK:
Write a professional reply email using the data above as evidence/context.
- Reference specific figures, dates, or order details where available.
- Match the tone specified.
- If data is missing, acknowledge politely and ask for clarification.
- Sign off as Asad Irfan, Senior Marketing Manager, Arooj Enterprises.

Output ONLY the email body (no subject line). Start directly with "Dear [Name]," or "Dear Team,".
"""

    print("\n[Router Step 2] Drafting reply with Gemini…")
    draft = _gemini(draft_prompt, temperature=0.4)
    return draft


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def route_email(email_text: str, sender: str = "unknown@email.com",
                subject: str = "No Subject",
                received_at: str | None = None) -> dict:
    """
    Full routing pipeline: store → route → execute → draft.

    Returns dict with:
      inbox_id, routing_plan, routing_result, reply_draft
    """
    if not received_at:
        received_at = datetime.datetime.now().isoformat()

    # ── Store incoming email ──────────────────────────────────────────────
    conn     = get_conn()
    msg_id   = hashlib.sha256(f"{sender}{subject}{received_at}".encode()).hexdigest()[:40]
    clean_subject = re.sub(r"^(Re|Fwd):", "", subject)
    thread_id = hashlib.sha256((sender + clean_subject).encode()).hexdigest()[:20]

    # Check if already stored
    existing = conn.execute("SELECT id FROM inbox WHERE message_id=?", (msg_id,)).fetchone()
    if existing:
        print(f"[Router] Email already in inbox (id={existing['id']}). Skipping re-process.")
        conn.close()
        return {"inbox_id": existing["id"], "status": "already_processed"}

    cur = conn.execute(
        """INSERT INTO inbox (message_id, sender, subject, body, received_at, thread_id, status, label)
           VALUES (?, ?, ?, ?, ?, ?, 'new', 'new')""",
        (msg_id, sender, subject, email_text, received_at, thread_id),
    )
    inbox_id = cur.lastrowid
    conn.commit()
    print(f"\n[Router] Email stored → inbox id={inbox_id}  thread={thread_id}")

    # ── Fetch thread history ──────────────────────────────────────────────
    thread_history = [dict(r) for r in conn.execute(
        "SELECT sender, subject, body, received_at FROM inbox WHERE thread_id=? AND id!=? ORDER BY received_at DESC LIMIT 5",
        (thread_id, inbox_id),
    ).fetchall()]

    # ── Step 1: Routing decision ──────────────────────────────────────────
    routing_plan = step1_routing_decision(email_text, sender, subject, thread_history)

    # ── Step 1b: Exact schema SQL Generation ────────────────────────────
    if routing_plan:
        routing_plan = step1b_generate_sql(email_text, sender, subject, routing_plan)

    # ── Step 2: Execute + Draft ───────────────────────────────────────────
    routing_result = {}
    reply_draft    = ""

    if routing_plan:
        reply_draft = step2_execute_and_draft(email_text, sender, subject, routing_plan)

        # Update inbox with reply draft and mark as under review
        conn.execute(
            """UPDATE inbox SET processed=1, routing_plan=?, reply_draft=?, status='under review', label='under review'
               WHERE id=?""",
            (json.dumps(routing_plan), reply_draft, inbox_id),
        )
        conn.commit()

    conn.close()

    return {
        "inbox_id":      inbox_id,
        "routing_plan":  routing_plan,
        "routing_result": routing_result,
        "reply_draft":   reply_draft,
    }
