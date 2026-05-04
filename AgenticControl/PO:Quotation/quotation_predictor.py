"""
quotation_predictor.py
======================
Quotation Information Predictor for TEXBASE PO system.

Given a `source_file` value (the original scanned document name, can be PDF or Image), this script:
  1. Fetches ALL matching rows from po_database.db.
  2. Uses Gemini 2.5 Flash to verify if the data is textile-related (AI-based).
  3. Sends ALL rows + FULL Pakistan market risk data in ONE Gemini API call
     (with Google Search grounding) to predict best-quote prices.
  4. Saves enriched rows into quotation_predictions.db with
     `predicted_price_usd` and `prediction_reasoning` columns.

Usage:
    python3 quotation_predictor.py --source "Screenshot 2026-03-06 at 4.01.20 PM.png')
    python3 quotation_predictor.py --source 'my_po.pdf') --table my_custom_table
    python3 quotation_predictor.py --list-tables
"""

from __future__ import annotations

import os
import re
import sys
import json
import sqlite3
import argparse
import datetime
import unicodedata

from google import genai
from google.genai import types

from dotenv import load_dotenv
load_dotenv(os.path.join(os.environ.get('WORKSPACE_ROOT', os.path.join(os.environ.get('WORKSPACE_ROOT', '.'), 'backend/.env'))))
# ═══════════════════════════════════════════════════════════════════
#  CONFIGURATION
# ═══════════════════════════════════════════════════════════════════

API_KEY         = os.environ.get("GEMINI_API_KEY_2")

SCRIPT_DIR      = os.path.join(os.environ.get('WORKSPACE_ROOT', '.'), 'AgenticControl/PO:Quotation')
PO_DB_PATH      = os.path.join(SCRIPT_DIR, 'po_database.db')
PRED_DB_PATH    = os.path.join(SCRIPT_DIR, 'quotation_predictions.db')
RISK_JSON_PATH  = os.path.join(os.environ.get('WORKSPACE_ROOT', '.'), 'Excel_Generator/Stats_data_collection/risk_factors.json')

# Gemini models
MODEL_VERIFY    = "gemini-2.5-flash"          # used for textile verification
MODEL_PREDICT   = "gemini-2.5-flash"          # primary: free-tier quota available
MODEL_PREDICT_ALT = "gemini-3-flash-preview"  # alt: use if primary quota is full


# ═══════════════════════════════════════════════════════════════════
#  GEMINI CLIENT
# ═══════════════════════════════════════════════════════════════════

client = genai.Client(api_key=API_KEY)


# ═══════════════════════════════════════════════════════════════════
#  DB HELPERS
# ═══════════════════════════════════════════════════════════════════

def _open_db(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _list_tables(conn: sqlite3.Connection) -> list[str]:
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    return [r[0] for r in cur.fetchall()]


def _table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    cur = conn.execute(f'PRAGMA table_info("{table}")')
    return [r["name"] for r in cur.fetchall()]


def _normalize_ws(s: str) -> str:
    """Normalize Unicode whitespace variants (e.g. narrow no-break \\u202f) to regular space."""
    return re.sub(r'[\s\u00a0\u202f\u2009\u2007\u2008\u200a]+', ' ', s).strip()


def _fetch_rows(conn: sqlite3.Connection, table: str, source_file: str | None = None) -> list[dict]:
    """Fetch rows by source_file — exact match first, then whitespace-normalized fallback. If source_file is absent, return all rows."""
    if not source_file:
        cur = conn.execute(f'SELECT * FROM "{table}"')
        return [dict(r) for r in cur.fetchall()]
        
    cur = conn.execute(f'SELECT * FROM "{table}" WHERE source_pdf = ?', (source_file,))
    rows = [dict(r) for r in cur.fetchall()]
    if rows:
        return rows
    # Whitespace-normalized fallback (handles \\u202f stored by macOS screenshot names)
    cur = conn.execute(f'SELECT * FROM "{table}"')
    all_rows = [dict(r) for r in cur.fetchall()]
    source_norm = _normalize_ws(source_file)
    return [r for r in all_rows if _normalize_ws(str(r.get("source_pdf", ""))) == source_norm]


# ═══════════════════════════════════════════════════════════════════
#  STEP 1 — TEXTILE VERIFICATION (AI-BASED via Gemini 2.5 Flash)
# ═══════════════════════════════════════════════════════════════════

def verify_textile_with_gemini(table: str, rows: list[dict], columns: list[str]) -> tuple[bool, str]:
    """
    Uses Gemini 2.5 Flash to determine if the table / its data represents
    textile-industry content.  Returns (is_textile: bool, reasoning: str).
    """
    print(f"\n[ STEP 1 — AI TEXTILE VERIFICATION (Gemini 2.5 Flash) ]")
    print("─" * 60)

    skip_sys = {"id", "embedding_id", "created_at"}
    data_cols = [c for c in columns if c not in skip_sys]

    # Build concise snapshot of table + sample rows
    sample_rows = rows[:5]
    rows_text = []
    for i, row in enumerate(sample_rows, 1):
        row_items = {c: row.get(c, "") for c in data_cols}
        rows_text.append(f"  Row {i}: {json.dumps(row_items, ensure_ascii=False)}")

    sample_text = "\n".join(rows_text)

    prompt = f"""You are a textile industry expert.
Analyze the following database table and determine whether it contains data related to
the TEXTILE INDUSTRY (fabric, yarn, cotton, garments, dyeing chemicals, bleaching agents,
finishing chemicals, apparel, fibers, or any textile manufacturing inputs/outputs).

Table name: {table}
Columns: {', '.join(data_cols)}

Sample rows:
{sample_text}

Answer with EXACTLY this JSON format (nothing else):
{{"is_textile": true_or_false, "confidence": "HIGH/MEDIUM/LOW", "reason": "one sentence explanation"}}
"""

    try:
        response = client.models.generate_content(
            model=MODEL_VERIFY,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.0)
        )
        raw = response.text.strip()
        raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.MULTILINE)
        raw = re.sub(r'```\s*$', '', raw, flags=re.MULTILINE).strip()
        result = json.loads(raw)
        is_textile = bool(result.get("is_textile", False))
        confidence = result.get("confidence", "?")
        reason     = result.get("reason", "")
        status = "✓ TEXTILE" if is_textile else "✗ NOT TEXTILE"
        print(f"  {status} [{confidence}] — {reason}\n")
        return is_textile, reason
    except Exception as e:
        print(f"  [WARN] Verification call failed ({e}). Proceeding anyway.")
        return True, "Verification skipped due to API error."


# ═══════════════════════════════════════════════════════════════════
#  STEP 2 — LOAD & FORMAT FULL RISK DATA
# ═══════════════════════════════════════════════════════════════════

def load_risk_factors() -> dict:
    if not os.path.exists(RISK_JSON_PATH):
        print(f"  [WARN] risk_factors.json not found at:\n  {RISK_JSON_PATH}")
        return {}
    with open(RISK_JSON_PATH, "r") as f:
        data = json.load(f)
    alerts = len(data.get("triggered_alerts", []))
    rules  = len(data.get("all_rules", []))
    print(f"  ✓ Loaded risk_factors.json  ({rules} rules, {alerts} active alerts)")
    return data


def format_full_market_summary(risk: dict) -> str:
    """
    Produce the most comprehensive possible market summary from risk_factors.json,
    covering every data field, every triggered alert, and every rule evaluation.
    """
    if not risk:
        return "(market data unavailable)"

    snap    = risk.get("data_snapshot", {})
    alerts  = risk.get("triggered_alerts", [])
    rules   = risk.get("all_rules", [])
    summary = risk.get("summary", {})
    gen_at  = risk.get("generated_at", "unknown")

    lines = []

    # ── Header ────────────────────────────────────────────────────
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("  PAKISTAN TEXTILE MARKET INTELLIGENCE REPORT")
    lines.append(f"  Generated: {gen_at}")
    lines.append(f"  Rules evaluated: {summary.get('total_rules_evaluated')}  |  "
                 f"Alerts: {summary.get('alerts_triggered')}  "
                 f"(HIGH: {summary.get('high_alerts')}, "
                 f"MEDIUM: {summary.get('medium_alerts')})")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    # ── Crude Oil / Energy ──────────────────────────────────────
    lines.append("\n  [ENERGY / CRUDE OIL]")
    lines.append(f"  Brent Crude   : ${snap.get('brent_price')}/bbl "
                 f"(prev: ${snap.get('brent_prev')}, "
                 f"Δ {snap.get('brent_change')} / {snap.get('brent_change_pct')}%)")
    lines.append(f"  Naphtha       : ${snap.get('naphtha_price')}/ton "
                 f"(Δ {snap.get('naphtha_change')} / {snap.get('naphtha_change_pct')}%)")

    # ── Cotton Markets ─────────────────────────────────────────
    lines.append("\n  [COTTON MARKETS]")
    lines.append(f"  ICE Cotton NY   : ${snap.get('ice_cotton_price')}/lb "
                 f"(prev: ${snap.get('ice_cotton_prev')}, Δ {snap.get('ice_cotton_change_pct')}%)")
    lines.append(f"  Cotlook A Index : {snap.get('cotlook_a_latest')} $/lb "
                 f"(as of {snap.get('cotlook_a_date')}, "
                 f"prev month: {snap.get('cotlook_a_prev_month')})")
    lines.append(f"  ZCE Cotton (CN) : {snap.get('zce_cotton_price')} CNY/ton "
                 f"(Δ {snap.get('zce_cotton_change')} / {snap.get('zce_cotton_change_pct')}%)")
    lines.append(f"  PK Cotton       : Rs. {snap.get('pk_cotton_per_kg')}/kg "
                 f"(40kg bale: Rs. {snap.get('pk_cotton_min_40kg')}–{snap.get('pk_cotton_max_40kg')})")

    # ── Yarn Prices (Pakistan) ─────────────────────────────────
    lines.append("\n  [YARN PRICES — PAKISTAN]")
    lines.append(f"  20s Carded avg  : Rs. {snap.get('yarn_20s_avg'):.1f}  "
                 f"(items: {', '.join(snap.get('yarn_20s_list', []))})")
    lines.append(f"  30s avg         : Rs. {snap.get('yarn_30s_avg'):.1f}")
    lines.append(f"  40CF Combed avg : Rs. {snap.get('yarn_40cf_avg'):.1f}")
    lines.append(f"  60CF Combed avg : Rs. {snap.get('yarn_60cf_avg'):.1f}")

    # ── China Yarn Futures ─────────────────────────────────────
    lines.append("\n  [CHINA YARN FUTURES (ZCE)]")
    lines.append(f"  ZCE Yarn        : {snap.get('china_yarn_price')} CNY/ton "
                 f"(Δ +{snap.get('china_yarn_change')} / {snap.get('china_yarn_change_pct')}%)")
    lines.append(f"  52-week low/high: {snap.get('china_yarn_52wk_low')} / {snap.get('china_yarn_52wk_high')}")

    # ── Chemicals: TPA & EG ────────────────────────────────────
    tpa = snap.get("tpa_regions", [])
    eg  = snap.get("eg_regions", [])
    if tpa:
        lines.append("\n  [TEREPHTHALIC ACID (TPA) — REGIONAL PRICES]")
        for r in tpa:
            lines.append(f"    {r['region']:<20} {r['price']}  ({r['change']})")
    if eg:
        lines.append("\n  [ETHYLENE GLYCOL (EG) — REGIONAL PRICES]")
        for r in eg:
            lines.append(f"    {r['region']:<20} {r['price']}  ({r['change']})")

    # ── Forex / Currency ───────────────────────────────────────
    lines.append("\n  [FOREX / CURRENCY — PAKISTAN]")
    lines.append(f"  USD/PKR interbank: {snap.get('usd_pkr')} "
                 f"({snap.get('usd_pkr_change_pct')}% change)")
    lines.append(f"  Open mkt buy/sell: {snap.get('open_usd_buy')} / {snap.get('open_usd_sell')}")
    lines.append(f"  EUR/PKR          : {snap.get('eur_pkr')}  |  EUR/USD: {snap.get('eur_usd')}")
    lines.append(f"  GBP buy (open)   : {snap.get('open_gbp_buy')}  |  "
                 f"CNY/PKR: {snap.get('cny_pkr')}")
    lines.append(f"  FX Reserves      : ${snap.get('fx_reserves')}M "
                 f"(prev: ${snap.get('fx_reserves_prev')}M, "
                 f"as of {snap.get('fx_reserves_date')})")

    # ── Interest Rates ─────────────────────────────────────────
    lines.append("\n  [INTEREST RATES — PAKISTAN]")
    lines.append(f"  SBP Policy rate  : {snap.get('pk_interest_rate')}%")
    lines.append(f"  Interbank rate   : {snap.get('pk_interbank_rate')}%")
    lines.append(f"  KIBOR 6M         : {snap.get('kibor_6m')}%  |  "
                 f"KIBID 6M: {snap.get('kibid_6m')}%  "
                 f"(as of {snap.get('kibor_date')})")
    lines.append(f"  Forward premia   : 1M={snap.get('fwd_1m_bid')} paise  |  "
                 f"3M={snap.get('fwd_3m_bid')}  |  6M={snap.get('fwd_6m_bid')}")

    # ── Weather ────────────────────────────────────────────────
    lines.append("\n  [WEATHER / CROP RISK — PAKISTAN]")
    lines.append(f"  Sindh : rain={snap.get('sindh_total_rain')}mm, "
                 f"max chance={snap.get('sindh_max_rain_chance')}%, "
                 f"max temp={snap.get('sindh_max_temp')}°C")
    lines.append(f"  Punjab: rain={snap.get('punjab_total_rain')}mm, "
                 f"max chance={snap.get('punjab_max_rain_chance')}%, "
                 f"max temp={snap.get('punjab_max_temp')}°C")

    # ── Active Triggered Alerts ────────────────────────────────
    lines.append("\n  [ACTIVE RISK ALERTS]")
    if alerts:
        for a in alerts:
            lines.append(f"  [{a['severity']:6}] [{a['rule_id']}] {a['rule_name']}")
            lines.append(f"           Condition : {a['condition']}")
            lines.append(f"           Action    : {a['recommendation']}")
    else:
        lines.append("  (none)")

    # ── All Rules Summary ──────────────────────────────────────
    lines.append("\n  [ALL RULES EVALUATED]")
    triggered_ids = {a["rule_id"] for a in alerts}
    for r in rules:
        flag = "🔴" if r["rule_id"] in triggered_ids else "🟢"
        lines.append(f"  {flag} [{r['rule_id']:20}] {r['rule_name']:<35} "
                     f"[{r.get('severity','?'):6}] {r['condition']}")

    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
#  STEP 3 — BUILD PROMPT (All rows batched, full market data)
# ═══════════════════════════════════════════════════════════════════

def _format_rows_for_prompt(rows: list[dict]) -> str:
    skip_cols = {"id", "embedding_id", "source_pdf", "created_at"}
    data_cols = [c for c in rows[0].keys() if c not in skip_cols]

    lines = ["| Row # | " + " | ".join(data_cols) + " |"]
    lines.append("| " + " | ".join(["---"] * (len(data_cols) + 1)) + " |")
    for i, row in enumerate(rows, start=1):
        vals = [str(row.get(c, "")) for c in data_cols]
        lines.append(f"| {i} | " + " | ".join(vals) + " |")
    return "\n".join(lines)


def build_prompt(rows: list[dict], market_summary: str, source_file: str) -> str:
    row_table = _format_rows_for_prompt(rows)

    prompt = f"""You are a senior pricing analyst for a Pakistani textile export company.
You have access to Google Search — use it to find CURRENT LIVE MARKET PRICES for each
item before making your prediction.

Your objective: Predict the BEST PRICE TO QUOTE TO THE CLIENT (in USD) for each
Purchase Order line item, taking into account:
  1. Current live market prices (search the web NOW for each product)
  2. The comprehensive Pakistan textile market intelligence data below
  3. A reasonable export profit margin of 8–15% for a Pakistani manufacturer
  4. Pakistan-specific cost factors: USD/PKR rate, energy prices, cotton/yarn costs,
     chemical input costs (naphtha, TPA, EG), and active supply chain risks

SOURCE DOCUMENT: {source_file}
TOTAL ROWS TO PRICE: {len(rows)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PO LINE ITEMS — ALL {len(rows)} ROWS (batch — price every row):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{row_table}

{market_summary}

PRICING INSTRUCTIONS:
  - Search for live market price of each item (e.g. "hydrogen peroxide 50% bulk price 2026")
  - Factor all active HIGH/MEDIUM risk alerts into your price cushion / margin
  - Use USD/PKR interbank rate to convert local PKR costs to USD
  - Apply 8–15% margin on top of estimated Total Landed Cost (raw material + energy + conversion)
  - For chemicals: check naphtha/TPA/EG prices as cost drivers
  - For yarn/cotton items: use Pakistan yarn prices + cotton futures
  - State clearly which live search result informed each price

RESPONSE FORMAT — Return ONLY a valid JSON array, NO markdown fences, NO extra text:
[
  {{
    "table_ref": "<string, the table this row came from>",
    "row_index": <int>,
    "item": "<item description>",
    "quantity": "<from PO>",
    "current_po_price": "<unit_price from PO>",
    "predicted_price_usd": "<number as string, e.g. 145.50>",
    "price_per": "<per kg / per unit / per meter — specify unit>",
    "margin_applied_pct": "<e.g. 12>",
    "currency": "USD",
    "live_source": "<URL or market source you searched>",
    "reasoning": "<3–4 sentences: live market rate found, cost build-up in PKR, margin, risk factors applied>"
  }}
]

Return exactly {len(rows)} objects in the array — one per PO row above.
"""
    return prompt


# ═══════════════════════════════════════════════════════════════════
#  STEP 4 — SINGLE BATCHED GEMINI CALL (Google Search grounded)
# ═══════════════════════════════════════════════════════════════════

def call_gemini_batched(prompt: str) -> list[dict]:
    """
    ONE Gemini API call with Google Search grounding for all rows.
    Tries MODEL_PREDICT first; falls back to MODEL_PREDICT_ALT on 429.
    Returns list of prediction dicts.
    """
    print(f"\n[ STEP 3 — GEMINI PRICE PREDICTION ]")
    print("─" * 60)
    print(f"  Model   : {MODEL_PREDICT}  (alt: {MODEL_PREDICT_ALT})")
    print(f"  Grounding : Google Search enabled")
    print(f"  Strategy  : ALL rows in ONE API call (minimum API usage)")

    grounding_tool = types.Tool(google_search=types.GoogleSearch())
    config = types.GenerateContentConfig(
        tools=[grounding_tool],
        temperature=0.1,
    )

    # Try primary model, fall back on quota exhaustion
    for model_name in [MODEL_PREDICT, MODEL_PREDICT_ALT]:
        try:
            print(f"  Calling  : {model_name} ...")
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config,
            )
            raw_text = response.text.strip()
            print(f"  ✓ Response received ({len(raw_text)} chars) from {model_name}")
            break
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                print(f"  [WARN] {model_name} quota exceeded — trying fallback...")
                continue
            else:
                raise
    else:
        print("  [ERROR] All models exhausted quota. Cannot generate predictions.")
        return []

    # Strip any accidental markdown code fences
    raw_text = re.sub(r'^```(?:json)?\s*', '', raw_text, flags=re.MULTILINE)
    raw_text = re.sub(r'```\s*$', '', raw_text, flags=re.MULTILINE).strip()

    try:
        predictions = json.loads(raw_text)
        if isinstance(predictions, list):
            print(f"  ✓ Parsed {len(predictions)} prediction(s) successfully.")
            return predictions
        else:
            print(f"  [WARN] Unexpected JSON structure — wrapping.")
            return [predictions]
    except json.JSONDecodeError as e:
        print(f"  [WARN] JSON parse error: {e}")
        print(f"  Raw (first 1000 chars):\n{raw_text[:1000]}")
        # Graceful fallback — store raw response as reasoning
        return [
            {"table_ref": "unknown", "row_index": i + 1, "predicted_price_usd": "N/A",
             "reasoning": raw_text[:800], "live_source": "parse error"}
            for i in range(20)   # arbitrary fallback length
        ]


# ═══════════════════════════════════════════════════════════════════
#  STEP 5 — SAVE TO PREDICTIONS DB
# ═══════════════════════════════════════════════════════════════════

def _sanitize(name: str) -> str:
    name = name.strip().lower()
    name = re.sub(r"[^a-z0-9_]", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return name or "col"


def save_predictions(rows: list[dict], predictions: list[dict],
                     source_table: str) -> str:
    """Write enriched rows with predictions to quotation_predictions.db."""
    pred_table = _sanitize(source_table) + "_predictions"

    # row_index → prediction lookup
    pred_map = {int(p.get("row_index", 0)): p for p in predictions if p.get("row_index")}

    conn = _open_db(PRED_DB_PATH)

    # Build column list from original rows (keep source_pdf, created_at)
    skip_system = {"id", "embedding_id"}
    orig_cols   = [c for c in rows[0].keys() if c not in skip_system] if rows else []

    system_ddl = ["id INTEGER PRIMARY KEY AUTOINCREMENT"]
    data_ddl   = [f'"{_sanitize(c)}" TEXT' for c in orig_cols]
    pred_ddl   = [
        '"predicted_price_usd" TEXT',
        '"price_per" TEXT',
        '"margin_applied_pct" TEXT',
        '"live_source" TEXT',
        '"prediction_reasoning" TEXT',
        '"prediction_timestamp" TEXT',
    ]
    ddl = (f'CREATE TABLE IF NOT EXISTS "{pred_table}" '
           f'({", ".join(system_ddl + data_ddl + pred_ddl)})')
    conn.execute(ddl)
    conn.commit()

    print(f"\n[ STEP 4 — SAVING TO PREDICTIONS DB ]")
    print("─" * 60)
    print(f"  Table  : {pred_table}")
    print(f"  DB     : {PRED_DB_PATH}")

    now      = datetime.datetime.utcnow().isoformat()
    inserted = 0

    for i, row in enumerate(rows, start=1):
        pred = pred_map.get(i, {})

        safe_orig_cols = [_sanitize(c) for c in orig_cols]
        extra_vals = [
            pred.get("predicted_price_usd", "N/A"),
            pred.get("price_per", ""),
            pred.get("margin_applied_pct", ""),
            pred.get("live_source", ""),
            pred.get("reasoning", ""),
            now,
        ]
        col_list = ", ".join(
            [f'"{c}"' for c in safe_orig_cols] +
            ['"predicted_price_usd"', '"price_per"', '"margin_applied_pct"',
             '"live_source"', '"prediction_reasoning"', '"prediction_timestamp"']
        )
        placeholders = ", ".join(["?"] * (len(safe_orig_cols) + 6))
        values = [str(row.get(c, "")) for c in orig_cols] + extra_vals

        conn.execute(
            f'INSERT INTO "{pred_table}" ({col_list}) VALUES ({placeholders})',
            values
        )
        inserted += 1

    conn.commit()
    conn.close()
    print(f"  ✓ {inserted} row(s) saved.")
    return pred_table


# ═══════════════════════════════════════════════════════════════════
#  MAIN PIPELINE
# ═══════════════════════════════════════════════════════════════════

def predict_quotation(source_file: str | None = None, table_name: str | None = None) -> dict:
    if source_file:
        source_file = os.path.basename(source_file)
    print(f"\n{'═' * 65}")
    print(f"  TEXBASE — Quotation Price Predictor")
    print(f"  Source Document : {source_file or 'N/A'}")
    print(f"  Target Tbl : {table_name or 'N/A'}")
    print(f"{'═' * 65}")

    if not os.path.exists(PO_DB_PATH):
        print(f"[ERROR] po_database.db not found: {PO_DB_PATH}")
        return {}

    po_conn    = _open_db(PO_DB_PATH)
    all_tables = _list_tables(po_conn)

    # ── Determine tables to process ──────────────────────────────
    print(f"\n[ STEP 0 — DATA FETCH ]")
    print("─" * 60)

    if table_name:
        tables_to_process = [table_name]
    elif source_file:
        tables_to_process = []
        for t in all_tables:
            if "source_pdf" in _table_columns(po_conn, t):
                rows = _fetch_rows(po_conn, t, source_file)
                if rows:
                    tables_to_process.append(t)
    else:
        print(f"  [ERROR] Neither source_file nor table_name provided.")
        po_conn.close()
        return {}

    if not tables_to_process:
        print(f"  [!] No valid tables found matching criteria.")
        po_conn.close()
        return {}

    print(f"  Tables : {tables_to_process}")

    # ── Load full risk / market data (ONCE) ───────────────────────
    print(f"\n[ STEP 0b — LOAD MARKET RISK DATA ]")
    print("─" * 60)
    risk = load_risk_factors()
    market_summary = format_full_market_summary(risk)

    results = []

    all_rows_to_predict = []
    
    # ── Fetch rows & Textile verification ──
    for tbl in tables_to_process:
        print(f"\n  ── Table: '{tbl}' ──")
        rows = _fetch_rows(po_conn, tbl, source_file)
        cols = _table_columns(po_conn, tbl)
        print(f"  Rows fetched : {len(rows)}")

        if not rows: continue

        # Step 1: AI Textile Verification
        is_textile, reason = verify_textile_with_gemini(tbl, rows, cols)
        if not is_textile:
            print("  [WARN] Proceeding despite non-textile classification (user override).")

        # Give each row a unified table_ref and a continuous row index
        for i, row in enumerate(rows, start=1):
            row["__table_ref__"] = tbl
            row["__row_index__"] = i
            
        all_rows_to_predict.extend(rows)

    if not all_rows_to_predict:
        print("  [!] No valid rows to process across all tables.")
        po_conn.close()
        return {}

    # Step 3: Build ONE prompt containing ALL rows from ALL tables
    print(f"\n  ── BATCHING {len(all_rows_to_predict)} ROWS ACROSS {len(tables_to_process)} TABLES ──")
    prompt = build_prompt(all_rows_to_predict, market_summary, source_file)
    predictions = call_gemini_batched(prompt)

    # Step 4: Persist — mapping predictions back to their originating tables
    for tbl in tables_to_process:
        tbl_rows = [r for r in all_rows_to_predict if r.get("__table_ref__") == tbl]
        if not tbl_rows: continue
        
        # Optionally, fallback routing: if model didn't provide table_ref but preserved original order
        # (Assuming model returns predictions strictly in the order they were provided)
        tbl_preds = []
        for p in predictions:
             if p.get("table_ref") == tbl:
                 tbl_preds.append(p)

        if len(tbl_preds) < len(tbl_rows) and len(predictions) == len(all_rows_to_predict):
             # Map purely by ordered index if table references are missing
             start_idx = all_rows_to_predict.index(tbl_rows[0])
             end_idx = start_idx + len(tbl_rows)
             tbl_preds = predictions[start_idx:end_idx]
             # Update inner row_index to match local table 1-based indexing so `save_predictions` finds them
             for offset, p in enumerate(tbl_preds, start=1):
                 p["row_index"] = offset

        # Strip our internal routing keys before saving
        for r in tbl_rows:
            r.pop("__table_ref__", None)
            r.pop("__row_index__", None)

        pred_table = save_predictions(tbl_rows, tbl_preds, tbl)
        results.append({"source_table": tbl, "prediction_table": pred_table, "rows": len(tbl_rows)})

    po_conn.close()

    # ── Final summary ─────────────────────────────────────────────
    print(f"\n{'═' * 65}")
    print(f"  COMPLETE — Quotation Predictions")
    for r in results:
        print(f"    {r['source_table']}")
        print(f"    → {r['prediction_table']}  ({r['rows']} rows)")
    print(f"  Predictions DB : {PRED_DB_PATH}")
    print(f"{'═' * 65}\n")

    # ── Print predictions to console ──────────────────────────────
    if results:
        print("  PREDICTED PRICES (summary):")
        print("  " + "─" * 60)
        conn2 = _open_db(PRED_DB_PATH)
        for r in results:
            pt   = r["prediction_table"]
            # Dynamically find a description-like column and a price column
            avail = [c[1] for c in conn2.execute(f'PRAGMA table_info("{pt}")').fetchall()]
            desc_col  = next((c for c in avail if "description" in c or "item" in c
                              or "product" in c), avail[1] if len(avail) > 1 else "id")
            price_col = next((c for c in avail if "unit_price" in c or "price" in c
                              and "predicted" not in c), None)
            qty_col   = next((c for c in avail if "quantity" in c or "qty" in c), None)

            sel_cols = ", ".join(filter(None, [
                f'"{desc_col}"',
                f'"{qty_col}"'   if qty_col   else None,
                f'"{price_col}"' if price_col else None,
                '"predicted_price_usd"',
                '"price_per"',
                '"margin_applied_pct"',
                '"prediction_reasoning"',
            ]))
            cur = conn2.execute(f'SELECT {sel_cols} FROM "{pt}"')
            for row in cur.fetchall():
                row = list(row)
                print(f"\n  Item       : {row[0]}")
                idx = 1
                if qty_col:
                    print(f"  Qty        : {row[idx]}"); idx += 1
                if price_col:
                    print(f"  PO Price   : {row[idx]}"); idx += 1
                print(f"  ▶ PREDICTED: ${row[idx]} {row[idx+1]}  (margin: {row[idx+2]}%)")
                print(f"  Reasoning  : {row[idx+3]}")
        conn2.close()

    return {"predictions_db": PRED_DB_PATH, "tables": results}


# ═══════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="TEXBASE Quotation Price Predictor — Gemini + Google Search"
    )
    parser.add_argument("--source", "-s", default=None,
                        help="source_file value to look up (e.g. 'my_po.pdf') or 'image.png'))")
    parser.add_argument("--table", "-t", default=None,
                        help="Specific table to query (auto-discovers if omitted)")
    parser.add_argument("--list-tables", action="store_true",
                        help="List all tables in po_database.db and exit")
    args = parser.parse_args()

    if args.list_tables:
        conn = _open_db(PO_DB_PATH)
        print("\nTables in po_database.db:")
        for t in _list_tables(conn):
            print(f"  • {t}")
        conn.close()
        return

    if not args.source and not args.table:
        print("[ERROR] You must provide either --source or --table (or both).")
        parser.print_help()
        sys.exit(1)

    predict_quotation(source_file=args.source, table_name=args.table)


if __name__ == "__main__":
    main()
