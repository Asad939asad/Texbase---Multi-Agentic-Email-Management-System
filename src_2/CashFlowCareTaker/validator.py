#!/usr/bin/python3
"""
validator.py — CashFlowCareTaker  (Layer C)
============================================
Three validation steps before any DB write:

  1. FX Normaliser   — converts any currency → USD + PKR using risk_factors.json
  2. Schema Enforcer — ensures description, amount, date are not null
  3. Human-in-the-loop — prints evidence, prompts "yes" to confirm

Public API
----------
  validate_and_save(analysis_result: dict, source_type: str) -> SaveResult dict
"""

from __future__ import annotations
import json
import os
import sys
import datetime

sys.path.insert(0, os.path.dirname(__file__))
from db_setup import get_conn
from vector_store import add_transaction

RISK_FACTORS_PATH = (
    "/Volumes/ssd2/TEXBASE/src/PO:Quotation/Stats_data_collection/risk_factors.json'))
)


# ══════════════════════════════════════════════════════════════════════════════
#  FX NORMALISER
# ══════════════════════════════════════════════════════════════════════════════

def _load_fx_rates() -> dict:
    """Load FX rates from risk_factors.json data_snapshot."""
    try:
        with open(RISK_FACTORS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        snap = data.get("data_snapshot", {})
        rates = {
            "USD": 1.0,
            "PKR": 1.0 / snap.get("usd_pkr", 278.716),   # PKR → USD
            "EUR": snap.get("eur_usd", 1.182),              # EUR → USD (approximate)
            "CNY": 1.0 / (snap.get("cny_pkr", 40.57) / snap.get("usd_pkr", 278.716)),
        }
        usd_pkr = snap.get("usd_pkr", 278.716)
        return {"rates_to_usd": rates, "usd_pkr": usd_pkr, "snapshot": snap}
    except Exception as e:
        print(f"  [FX] Warning: could not load risk_factors.json: {e}")
        return {"rates_to_usd": {"USD": 1.0, "PKR": 1/278.716, "EUR": 1.182, "CNY": 0.138},
                "usd_pkr": 278.716, "snapshot": {}}


def normalise_fx(parsed: dict) -> dict:
    """
    Add amount_usd, amount_pkr, fx_rate_used to parsed dict.
    Returns updated parsed dict.
    """
    fx      = _load_fx_rates()
    currency = (parsed.get("currency") or "USD").upper()
    amount  = float(parsed.get("amount") or 0)

    rate_to_usd = fx["rates_to_usd"].get(currency, 1.0)
    usd_pkr     = fx["usd_pkr"]

    amount_usd = round(amount * rate_to_usd, 4)
    amount_pkr = round(amount_usd * usd_pkr, 2)

    snap = fx["snapshot"]
    print(f"\n[FX] {amount:,.2f} {currency} → "
          f"${amount_usd:,.4f} USD | ₨{amount_pkr:,.2f} PKR")
    print(f"     Rates from risk_factors.json: usd_pkr={snap.get('usd_pkr')}, "
          f"eur_pkr={snap.get('eur_pkr')}, cny_pkr={snap.get('cny_pkr')}")

    return {
        **parsed,
        "amount_usd":   amount_usd,
        "amount_pkr":   amount_pkr,
        "fx_rate_used": rate_to_usd,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  SCHEMA ENFORCER
# ══════════════════════════════════════════════════════════════════════════════

def enforce_schema(parsed: dict) -> list[str]:
    """
    Check mandatory fields. Returns list of validation errors (empty = OK).
    """
    errors = []
    if not parsed.get("description", "").strip():
        errors.append("description is null/empty")
    if not parsed.get("amount") and parsed.get("amount") != 0:
        errors.append("amount is null")
    if not parsed.get("date", "").strip():
        errors.append("date is null/empty")
    return errors


# ══════════════════════════════════════════════════════════════════════════════
#  HUMAN-IN-THE-LOOP
# ══════════════════════════════════════════════════════════════════════════════

def _print_evidence(parsed: dict, similar_entries: list, candidates: list) -> None:
    """Display all evidence before asking the user to confirm."""
    print("\n" + "═" * 65)
    print("  EVIDENCE SUMMARY — Please review before confirming")
    print("═" * 65)
    print(f"  Type         : {parsed.get('transaction_type', '?').upper()}")
    print(f"  Description  : {parsed.get('description', '?')}")
    print(f"  Counterparty : {parsed.get('counterparty', '?')}")
    print(f"  Amount (raw) : {parsed.get('amount_raw', '?')}")
    print(f"  Amount (USD) : ${parsed.get('amount_usd', 0):,.4f}")
    print(f"  Amount (PKR) : ₨{parsed.get('amount_pkr', 0):,.2f}")
    print(f"  FX Rate used : {parsed.get('fx_rate_used', '?')}")
    print(f"  Date         : {parsed.get('date', '?')}")
    print(f"  Confidence   : {parsed.get('confidence', '?')}")
    if parsed.get("notes"):
        print(f"  Notes        : {parsed.get('notes')}")

    if similar_entries:
        print(f"\n  VECTOR DB MATCHES ({len(similar_entries)}):")
        for h in similar_entries[:3]:
            print(f"    [{h['distance']:.3f}] {h['text'][:70]}")

    if candidates:
        print(f"\n  EXISTING DB MATCHES ({len(candidates)}):")
        for c in candidates:
            print(f"    {c.get('source_table','?')} | {c.get('counterparty','?')} | "
                  f"{c.get('amount_raw','?')} | {c.get('date','?')}")

    print("═" * 65)


def human_confirm(parsed: dict, similar_entries: list, candidates: list, auto_confirm: bool = False) -> bool:
    """Show evidence and ask user to type 'yes' to confirm save."""
    _print_evidence(parsed, similar_entries, candidates)
    if auto_confirm:
        print("\n  [Validator] Auto-confirmed by Superagent. Proceeding to save.")
        return True
    try:
        answer = input("\n  ▶ Type 'yes' to SAVE to database, or anything else to CANCEL: ").strip().lower()
        return answer in ("yes", "y")
    except (EOFError, KeyboardInterrupt):
        print("\n  Cancelled.")
        return False


# ══════════════════════════════════════════════════════════════════════════════
#  SAVE TO DB
# ══════════════════════════════════════════════════════════════════════════════

def _save_record(parsed: dict, source_type: str, vector_match: str) -> int:
    """Insert validated record into intakes or outtakes. Returns row id."""
    table = "intakes" if parsed.get("transaction_type") == "intake" else "outtakes"
    conn  = get_conn()
    cur   = conn.execute(
        f"""INSERT INTO {table}
            (description, amount_raw, amount_usd, amount_pkr, currency,
             fx_rate_used, date, source, counterparty, vector_match)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            parsed.get("description", ""),
            parsed.get("amount_raw", ""),
            parsed.get("amount_usd"),
            parsed.get("amount_pkr"),
            parsed.get("currency", ""),
            parsed.get("fx_rate_used"),
            parsed.get("date", ""),
            source_type,
            parsed.get("counterparty", ""),
            vector_match,
        ),
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def validate_and_save(analysis_result: dict, source_type: str = "manual", auto_confirm: bool = False) -> dict:
    """
    Layer C entry point.

    Parameters
    ----------
    analysis_result : output of gemini_analyst.analyse()
    source_type     : string label for the source column

    Returns
    -------
    dict  {saved: bool, table: str, row_id: int, errors: list}
    """
    parsed         = analysis_result.get("parsed", {})
    similar_entries = analysis_result.get("similar_entries", [])
    candidates     = analysis_result.get("candidates", [])

    if analysis_result.get("conflict"):
        print(f"\n[Validator] HIGH CONFLICT detected (id={analysis_result.get('conflict_id')}).")
        print("  This transaction has been saved to the conflicts table for manual review.")
        return {"saved": False, "table": "conflicts",
                "row_id": analysis_result.get("conflict_id"), "errors": []}

    if analysis_result.get("error"):
        print(f"\n[Validator] Cannot proceed: {analysis_result['error']}")
        return {"saved": False, "table": None, "row_id": None,
                "errors": [analysis_result["error"]]}

    # ── Step 1: FX Normalise ───────────────────────────────────────────────
    parsed = normalise_fx(parsed)

    # ── Step 2: Schema Enforce ─────────────────────────────────────────────
    errors = enforce_schema(parsed)
    if errors:
        print(f"\n[Validator] Schema errors: {errors}")
        return {"saved": False, "table": None, "row_id": None, "errors": errors}

    # ── Step 3: Human-in-the-loop ──────────────────────────────────────────
    confirmed = human_confirm(parsed, similar_entries, candidates, auto_confirm=auto_confirm)
    if not confirmed:
        print("\n  [Validator] Save cancelled by user.")
        return {"saved": False, "table": None, "row_id": None, "errors": ["User cancelled"]}

    # ── Save ───────────────────────────────────────────────────────────────
    vector_match = similar_entries[0]["text"][:120] if similar_entries else ""
    table = "intakes" if parsed.get("transaction_type") == "intake" else "outtakes"
    row_id = _save_record(parsed, source_type, vector_match)

    # ── Add to vector store for future searches ────────────────────────────
    vec_text = (
        f"{table.upper()} | {parsed.get('counterparty','')} | "
        f"{parsed.get('description','')} | {parsed.get('amount_raw','')} | "
        f"{parsed.get('date','')}"
    )
    add_transaction(vec_text, {
        "type":         table,
        "counterparty": parsed.get("counterparty", ""),
        "currency":     parsed.get("currency", ""),
        "date":         parsed.get("date", ""),
    })

    print(f"\n  ✅ Saved to '{table}' (id={row_id})")
    return {"saved": True, "table": table, "row_id": row_id, "errors": []}
