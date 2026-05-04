#!/usr/bin/python3
"""
add_vectors.py — CashFlowCareTaker
====================================
Standalone CLI to bulk-ingest transaction descriptions into the vector store.

Usage
-----
  # Interactive: paste one line per entry, blank line to finish
  /Volumes/ssd2/TEXBASE/venv/bin/python3 add_vectors.py

  # From a text file (one entry per line)
  /Volumes/ssd2/TEXBASE/venv/bin/python3 add_vectors.py --file entries.txt

  # From existing cashflow.db intakes/outtakes (backfill)
  /Volumes/ssd2/TEXBASE/venv/bin/python3 add_vectors.py --backfill
"""

from __future__ import annotations
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from vector_store import add_transaction, get_collection
from db_setup import get_conn


def backfill_from_db() -> None:
    """Add all existing intakes + outtakes to the vector store."""
    conn = get_conn()
    added = 0
    for table in ("intakes", "outtakes"):
        rows = conn.execute(
            f"SELECT description, amount_raw, currency, date, counterparty, '{table}' AS type FROM {table}"
        ).fetchall()
        for row in rows:
            text = (
                f"{row['type'].upper()} | {row['counterparty'] or ''} | "
                f"{row['description']} | {row['amount_raw'] or ''} | {row['date']}"
            )
            meta = {
                "type":         row["type"],
                "counterparty": row["counterparty"] or "",
                "currency":     row["currency"] or "",
                "date":         row["date"],
            }
            add_transaction(text, meta)
            added += 1
    conn.close()
    print(f"\n[add_vectors] Backfilled {added} entries from cashflow.db')))


def add_from_file(path: str) -> None:
    """Add entries from a plain-text file (one per line)."""
    with open(path, encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip()]
    for line in lines:
        add_transaction(line)
    print(f"\n[add_vectors] Added {len(lines)} entries from {path}")


def interactive_add() -> None:
    """Interactive mode: user types entries, blank line to finish."""
    print("Enter one transaction description per line. Blank line to finish.\n")
    entries = []
    while True:
        line = input("> ").strip()
        if not line:
            break
        entries.append(line)
    for entry in entries:
        add_transaction(entry)
    print(f"\n[add_vectors] Added {len(entries)} entries.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bulk-add entries to CashFlow vector store")
    parser.add_argument("--file",     help="Path to text file with one entry per line")
    parser.add_argument("--backfill", action="store_true", help="Backfill from cashflow.db')))
    args = parser.parse_args()

    col = get_collection()
    print(f"[add_vectors] Vector store has {col.count()} existing entry/entries.\n")

    if args.backfill:
        backfill_from_db()
    elif args.file:
        add_from_file(args.file)
    else:
        interactive_add()
