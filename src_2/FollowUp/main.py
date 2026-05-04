#!/usr/bin/python3
"""
main.py — FollowUp Agent CLI
==============================
Usage:
  # Pick ONE new (unprocessed) inbox email and route it
  /usr/bin/python3 main.py --run

  # Ingest + process an email from a .txt file
  /usr/bin/python3 main.py --email email_body.txt --from "client@company.com" --subject "Invoice #102"

  # Simulate with raw text (testing)
  /usr/bin/python3 main.py --simulate "Best Threads asking about payment status for invoice #102"

  # List inbox emails (NEW emails highlighted)
  /usr/bin/python3 main.py --list

  # Show reply draft for a specific inbox ID
  /usr/bin/python3 main.py --draft 1

  # Initialise databases only
  /usr/bin/python3 main.py --init
"""

from __future__ import annotations
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from db_setup import init_db, get_conn
from router   import route_email


def cmd_list() -> None:
    """Print inbox emails — [NEW] marks unprocessed (processed=0) rows."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, sender, subject, status, label, processed, received_at FROM inbox ORDER BY id DESC LIMIT 30"
    ).fetchall()
    conn.close()
    if not rows:
        print("Inbox is empty.")
        return
    new_count = sum(1 for r in rows if r['label'] == 'new')
    print(f"\n  Inbox ({len(rows)} emails, {new_count} new)")
    print(f"\n{'ID':<5} {'LABEL':<8} {'STATUS':<10} {'FROM':<30} {'SUBJECT'}")
    print("─"*85)
    for r in rows:
        label = f"[{r['label'].upper()}]" if r['label'] == 'new' else r['label'] or ''
        print(f"{r['id']:<5} {label:<8} {r['status']:<10} {(r['sender'] or '')[:28]:<30} {r['subject']}") 


def cmd_run_next() -> None:
    """
    Fetch the OLDEST unprocessed email (processed=0) from inbox
    and run the full routing pipeline on it.
    """
    conn = get_conn()
    row  = conn.execute(
        "SELECT * FROM inbox WHERE processed = 0 ORDER BY id ASC LIMIT 1"
    ).fetchone()
    conn.close()

    if not row:
        print("\n  ✅ No new emails to process. Inbox is up to date.")
        return

    email_id = row['id']
    print(f"\n{'═'*65}")
    print(f"  FollowUp Agent — Processing Queued Email")
    print(f"  Inbox ID : {email_id}")
    print(f"  From     : {row['sender']}")
    print(f"  Subject  : {row['subject']}")
    print(f"  Received : {row['received_at']}")
    print(f"{'═'*65}")

    # Import here to avoid circular import at module top
    from router import step1_routing_decision, step1b_generate_sql, step2_execute_and_draft
    import json

    # Fetch thread history for context
    conn2 = get_conn()
    thread_history = [dict(r) for r in conn2.execute(
        "SELECT sender, subject, body, received_at FROM inbox "
        "WHERE thread_id=? AND id!=? ORDER BY received_at DESC LIMIT 5",
        (row['thread_id'], email_id),
    ).fetchall()]

    # Step 1: routing decision
    routing_plan = step1_routing_decision(
        row['body'], row['sender'], row['subject'], thread_history
    )

    reply_draft = ""
    if routing_plan:
        # Step 1b: schema-aware SQL generation
        routing_plan = step1b_generate_sql(row['body'], row['sender'], row['subject'], routing_plan)

        # Step 2: execute SQL + draft reply
        reply_draft = step2_execute_and_draft(
            row['body'], row['sender'], row['subject'], routing_plan
        )
        
        # Save draft + mark processed
        conn2.execute(
            "UPDATE inbox SET processed=1, routing_plan=?, reply_draft=?, status='under review', label='under review' WHERE id=?",
            (json.dumps(routing_plan), reply_draft, email_id),
        )
        conn2.commit()

    conn2.close()

    print(f"\n{'═'*65}")
    if reply_draft:
        print(f"  ✅ Done. inbox_id={email_id} → status: under review")
        print(f"\n  DRAFT REPLY:")
        print(f"  {'─'*60}")
        print("  " + "\n  ".join(reply_draft.splitlines()))
        print(f"  {'─'*60}")
        print(f"\n  View again:  python3 main.py --draft {email_id}")
    else:
        print(f"  ⚠️  Routed but draft could not be generated (inbox_id={email_id}).")
    print(f"{'═'*65}")


def cmd_show_draft(inbox_id: int) -> None:
    """Print the reply draft and original email for a specific inbox ID."""
    conn = get_conn()
    row  = conn.execute("SELECT body, sender, subject, reply_draft FROM inbox WHERE id=?",
                        (inbox_id,)).fetchone()
    conn.close()
    if not row or not row['reply_draft']:
        print(f"No drafted reply found for inbox id={inbox_id}")
        return
    print(f"\n{'═'*65}")
    print(f"  ORIGINAL EMAIL (inbox_id={inbox_id})")
    print(f"{'═'*65}")
    print(f"\n{row['body']}")
    
    print(f"\n{'═'*65}")
    print(f"  DRAFTED REPLY (Status: Under Review)")
    print(f"{'═'*65}")
    print(f"  To     : {row['sender']}")
    print(f"  Subject: Re: {row['subject']}")
    print(f"\n{row['reply_draft']}")
    print(f"{'═'*65}")



def main() -> None:
    parser = argparse.ArgumentParser(
        prog="FollowUp Agent",
        description="LLM-powered email routing and reply drafting",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--run",      action="store_true", help="Process next NEW (unprocessed) inbox email")
    group.add_argument("--email",    metavar="FILE",  help="Ingest + process email from .txt file")
    group.add_argument("--simulate", metavar="TEXT",  help="Raw email text for simulation/testing")
    group.add_argument("--list",     action="store_true", help="List inbox emails ([NEW] = unprocessed)")
    group.add_argument("--draft",    metavar="ID",    type=int, help="Show draft for inbox ID")
    group.add_argument("--init",     action="store_true", help="Initialise DB only")

    parser.add_argument("--from",    dest="sender",  default="unknown@email.com", help="Sender email address")
    parser.add_argument("--subject", default="No Subject", help="Email subject line")

    args = parser.parse_args()

    # Always ensure DB exists
    init_db()

    if args.init:
        print("✅ Databases initialised.")
        return

    if args.run:
        cmd_run_next()
        return

    if args.list:
        cmd_list()
        return

    if args.draft is not None:
        cmd_show_draft(args.draft)
        return

    # ── Process email ─────────────────────────────────────────────────────
    if args.email:
        path = os.path.abspath(args.email)
        if not os.path.isfile(path):
            print(f"❌ File not found: {path}")
            sys.exit(1)
        with open(path, encoding="utf-8") as f:
            email_text = f.read()
        source_label = f"file:{os.path.basename(path)}"
    else:
        email_text   = args.simulate
        source_label = "simulate"

    print(f"\n{'═'*65}")
    print(f"  FollowUp Agent — Processing Email")
    print(f"  From   : {args.sender}")
    print(f"  Subject: {args.subject}")
    print(f"{'═'*65}")

    result = route_email(
        email_text  = email_text,
        sender      = args.sender,
        subject     = args.subject,
    )

    print(f"\n{'═'*65}")
    if result.get("reply_draft"):
        print(f"  ✅ Done. Inbox id={result['inbox_id']} | Status: under review")
        print(f"\n  DRAFT REPLY:")
        print(f"  {'─'*60}")
        print("  " + "\n  ".join(result["reply_draft"].splitlines()))
        print(f"  {'─'*60}")
        print(f"\n  View again anytime:  python3 main.py --draft {result['inbox_id']}")
    else:
        print(f"  ⚠️  Email stored (id={result.get('inbox_id')}) but draft could not be generated.")
    print(f"{'═'*65}")


if __name__ == "__main__":
    main()
