#!/usr/bin/python3
"""
main.py — CashFlowCareTaker  (Orchestrator)
=============================================
CLI entry point that wires together all 3 layers.

Usage
-----
  # Plain text
  /Volumes/ssd2/TEXBASE/venv/bin/python3 main.py --text "Received 50,000 PKR from Best Threads"

  # PDF invoice
  /Volumes/ssd2/TEXBASE/venv/bin/python3 main.py --file /path/to/invoice.pdf

  # Image receipt
  /Volumes/ssd2/TEXBASE/venv/bin/python3 main.py --file /path/to/receipt.jpg

  # Email body saved as .txt
  /Volumes/ssd2/TEXBASE/venv/bin/python3 main.py --email /path/to/email_body.txt

  # Initialise DB only
  /Volumes/ssd2/TEXBASE/venv/bin/python3 main.py --init
"""

from __future__ import annotations
import argparse
import os
import sys

# ── Ensure local modules importable ───────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

from db_setup    import init_db
from intake      import process_input
from gemini_analyst import analyse
from validator   import validate_and_save


def run(source: str, input_type: str = "auto", auto_confirm: bool = False) -> None:
    """Full 3-layer pipeline."""
    print("\n" + "═"*65)
    print("  CashFlowCareTaker — 3-Layer Pipeline")
    print("═"*65)

    # ── Layer A: Intake & Semantic Search ─────────────────────────────────
    print("\n[ LAYER A ] Intake & Semantic Search")
    intake_result = process_input(source, input_type=input_type)

    if not intake_result.get("raw_text"):
        print("\n❌ Could not extract any text from input. Aborting.")
        return

    # ── Layer B: Dual-Code Gemini Logic ───────────────────────────────────
    print("\n[ LAYER B ] Dual-Code Gemini Analysis")
    analysis_result = analyse(intake_result)

    if not analysis_result.get("parsed"):
        print("\n❌ Gemini could not parse a transaction. Aborting.")
        return

    if analysis_result.get("conflict"):
        print(f"\n⚠️  HIGH CONFLICT — transaction NOT saved.")
        print(f"   Conflict ID: {analysis_result.get('conflict_id')}")
        print("   Review conflicts table to resolve manually.")
        return

    # ── Layer C: Truth Validator ──────────────────────────────────────────
    print("\n[ LAYER C ] Truth Validator")
    result = validate_and_save(analysis_result, source_type=input_type, auto_confirm=auto_confirm)

    # ── Summary ───────────────────────────────────────────────────────────
    print("\n" + "═"*65)
    if result.get("saved"):
        print(f"  ✅ Transaction saved → {result['table']} (id={result['row_id']})")
    elif result["table"] == "conflicts":
        print(f"  ⚠️  Conflict logged → id={result['row_id']}")
    else:
        errs = ", ".join(result.get("errors", []))
        print(f"  ❌ Not saved. Reason: {errs}")
    print("═"*65)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="CashFlowCareTaker",
        description="Intelligent cash flow tracking for textile business",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--text",  metavar="TEXT",  help="Plain text transaction description")
    group.add_argument("--file",  metavar="PATH",  help="PDF or image file path (auto-detected)")
    group.add_argument("--email", metavar="PATH",  help="Email body saved as .txt file")
    group.add_argument("--init",  action="store_true", help="Initialise database and exit")
    parser.add_argument("--auto-confirm", action="store_true", help="Bypass human validation prompt")

    args = parser.parse_args()

    # Always ensure DB exists
    init_db()

    if args.init:
        print("✅ Database initialised.")
        return

    if args.text:
        run(args.text, input_type="text", auto_confirm=args.auto_confirm)

    elif args.file:
        path = os.path.abspath(args.file)
        if not os.path.isfile(path):
            print(f"❌ File not found: {path}")
            sys.exit(1)
        run(path, input_type="auto", auto_confirm=args.auto_confirm)

    elif args.email:
        path = os.path.abspath(args.email)
        if not os.path.isfile(path):
            print(f"❌ File not found: {path}")
            sys.exit(1)
        with open(path, encoding="utf-8") as f:
            body = f.read()
        run(body, input_type="email", auto_confirm=args.auto_confirm)


if __name__ == "__main__":
    main()
