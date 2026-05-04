#!/usr/bin/python3
"""
gemini_analyst.py — CashFlowCareTaker  (Layer B)
==================================================
Dual-step Gemini analysis:

  Step 1 — Candidate Extraction:
    Gemini parses raw text + similar vector entries + DB schema context
    → returns structured JSON: {type, description, amount, currency, date, counterparty}

  Step 2 — Conflict Resolution:
    SQL queries intakes/outtakes for any existing record matching same
    amount AND counterparty. If ≥2 matches → HIGH_CONFLICT → saved to
    conflicts table. Pipeline stops — no further processing.

Public API
----------
  analyse(intake_result: dict) -> AnalysisResult dict
"""

from __future__ import annotations
import json
import os
import re
import sys
import datetime

sys.path.insert(0, os.path.dirname(__file__))
from db_setup import get_conn

from google import genai
from google.genai import types

GEMINI_API_KEY = "AIzaSyBNpkJkdsEHFDezctWxPKhAuFrIfFcNy1s"
client         = genai.Client(api_key=GEMINI_API_KEY)

DB_SCHEMA = """
Tables available:
  intakes(id, description, amount_raw, amount_usd, amount_pkr, currency, fx_rate_used,
          date, source, counterparty, vector_match, created_at)
  outtakes(id, description, amount_raw, amount_usd, amount_pkr, currency, fx_rate_used,
           date, source, counterparty, vector_match, created_at)
  conflicts(id, original_input, candidates_json, conflict_reason, status, created_at)
"""


def _call_gemini(prompt: str) -> str:
    """Single Gemini call, returns raw text. Uses gemini-2.5-flash."""
    try:
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.1),
        )
        return resp.text.strip()
    except Exception as e:
        print(f"  [Gemini] Error: {e}")
        return ""


def _parse_json_from_response(text: str) -> dict:
    """Strip markdown fences and parse JSON."""
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"```\s*$", "", text, flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


def _step1_extract(raw_text: str, similar_entries: list) -> dict:
    """
    Step 1: Ask Gemini to parse the transaction from raw input.
    Returns structured transaction dict.
    """
    similar_text = "\n".join(
        f"  - [{h['distance']:.2f}] {h['text']}" for h in (similar_entries or [])
    ) or "  (none)"

    prompt = f"""You are a financial data extraction agent for a Pakistani textile business.

## DATABASE SCHEMA
{DB_SCHEMA}

## SIMILAR PAST TRANSACTIONS (from vector DB — use to resolve abbreviations / counterparty names)
{similar_text}

## RAW INPUT TO ANALYSE
{raw_text}

## TASK
Extract the financial transaction from the raw input. Use the similar past transactions
to resolve abbreviations (e.g. "BT" likely means "Best Threads" if that appears in similar entries).

Return ONLY a raw JSON object matching this exact schema:
{{
  "transaction_type": "intake" or "outtake",
  "description":      "clear human-readable description (NOT NULL)",
  "amount":           123456.78,
  "amount_raw":       "50,000 PKR" (as written in source),
  "currency":         "PKR" or "USD" or "EUR" or "CNY",
  "date":             "YYYY-MM-DD" (NOT NULL, use today if not found),
  "counterparty":     "company or person name",
  "confidence":       "high" or "medium" or "low",
  "notes":            "any caveats or assumptions made"
}}

Do not return anything else. No explanation."""

    print("\n[Gemini Step 1] Extracting transaction…")
    raw = _call_gemini(prompt)
    parsed = _parse_json_from_response(raw)
    if parsed:
        print(f"  ✓ Extracted: {parsed.get('transaction_type','?').upper()} | "
              f"{parsed.get('counterparty','?')} | "
              f"{parsed.get('amount_raw', parsed.get('amount','?'))} | "
              f"{parsed.get('date','?')}")
    else:
        print("  [WARN] Gemini returned unparseable JSON.")
    return parsed


def _step2_conflict_check(parsed: dict) -> list:
    """
    Step 2: SQL query to find existing records with same amount + counterparty.
    Returns list of matching rows (conflict candidates).
    """
    amount      = parsed.get("amount")
    counterparty = parsed.get("counterparty", "")
    if not amount or not counterparty:
        return []

    conn = get_conn()
    candidates = []
    for table in ("intakes", "outtakes"):
        rows = conn.execute(
            f"""SELECT id, description, amount_raw, date, counterparty, '{table}' AS source_table
                FROM {table}
                WHERE counterparty LIKE ?
                  AND ABS(amount_usd - ?) < 1.0
             """,
            (f"%{counterparty}%", float(amount)),
        ).fetchall()
        candidates.extend([dict(r) for r in rows])
    conn.close()
    return candidates


def _save_conflict(raw_text: str, candidates: list, reason: str) -> int:
    """Save HIGH_CONFLICT to conflicts table. Returns new conflict id."""
    conn = get_conn()
    cur  = conn.execute(
        "INSERT INTO conflicts (original_input, candidates_json, conflict_reason) VALUES (?, ?, ?)",
        (raw_text, json.dumps(candidates, ensure_ascii=False), reason),
    )
    conn.commit()
    conflict_id = cur.lastrowid
    conn.close()
    print(f"\n  ⚠️  HIGH CONFLICT — saved to conflicts table (id={conflict_id}).")
    print(f"      Reason: {reason}")
    return conflict_id


def analyse(intake_result: dict) -> dict:
    """
    Layer B entry point.

    Parameters
    ----------
    intake_result : output of intake.process_input()

    Returns
    -------
    dict with keys:
      parsed          : extracted transaction fields
      conflict        : True/False
      conflict_id     : int (set if conflict)
      candidates      : list of conflicting DB rows
      raw_text        : passthrough
      similar_entries : passthrough
    """
    raw_text       = intake_result.get("raw_text", "")
    similar_entries = intake_result.get("similar_entries", [])

    # ── Step 1: Extract ────────────────────────────────────────────────────
    parsed = _step1_extract(raw_text, similar_entries)
    if not parsed:
        return {
            "parsed":          {},
            "conflict":        False,
            "conflict_id":     None,
            "candidates":      [],
            "raw_text":        raw_text,
            "similar_entries": similar_entries,
            "error":           "Gemini could not parse the transaction.",
        }

    # ── Step 2: Conflict check ─────────────────────────────────────────────
    print("\n[Gemini Step 2] Checking for conflicts in DB…")
    candidates = _step2_conflict_check(parsed)

    if len(candidates) >= 2:
        reason = (
            f"Found {len(candidates)} existing records matching "
            f"counterparty='{parsed.get('counterparty')}' and "
            f"amount≈{parsed.get('amount')} {parsed.get('currency')}"
        )
        conflict_id = _save_conflict(raw_text, candidates, reason)
        return {
            "parsed":          parsed,
            "conflict":        True,
            "conflict_id":     conflict_id,
            "candidates":      candidates,
            "raw_text":        raw_text,
            "similar_entries": similar_entries,
        }

    print(f"  ✓ No conflict ({len(candidates)} match(es) found — below threshold).")
    return {
        "parsed":          parsed,
        "conflict":        False,
        "conflict_id":     None,
        "candidates":      candidates,
        "raw_text":        raw_text,
        "similar_entries": similar_entries,
    }
