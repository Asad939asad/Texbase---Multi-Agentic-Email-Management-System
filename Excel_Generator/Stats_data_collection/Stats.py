#!/usr/bin/python3
"""
TEXBASE Risk Factor Analysis Engine
=====================================
Reads all scraped market data JSONs/CSVs and evaluates business rules
across categories: Cotton, Yarn, Chemicals, Forex, Strategic Sourcing.
Outputs a risk_factors.json with triggered alerts, severity, and recommendations.
"""
import json
import csv
import os
import re
import requests
from datetime import datetime

# ── Paths ───────────────────────────────────────────────────────────────────
BASE = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(BASE, 'risk_factors.json')

DATA_FILES = {
    "brent_oil":        os.path.join(BASE, "BrentOIL", 'brent_oil.json'),
    "china_yarn":       os.path.join(BASE, "ChinaYarn", 'yarn_index_china.json'),
    "cotlook_a":        os.path.join(BASE, "CotlookA_Index", 'cotlook_a_index.json'),
    "cotton_global":    os.path.join(BASE, "Cotton_Global_rate", 'cotton_prices.json'),
    "cotton_pakistan":   os.path.join(BASE, "CottonPakistan", 'cotton_pakistan.json'),
    "forex":            os.path.join(BASE, "Forex", 'forex_data.json'),
    "glycol_tpa":       os.path.join(BASE, "glycol_terephthalic", 'glycol_terephthalic.json'),
    "naphthapreis":     os.path.join(BASE, "napthaprene_index", 'naphthapreis.json'),
    "weather":          os.path.join(BASE, "Weather_Forecast", 'pakistan_16day_detailed_rain.csv'),
    "yarn_pakistan":     os.path.join(BASE, "YarnPakistan", 'yarn_prices.json'),
    "zce_cotton":       os.path.join(BASE, "ZCE_Cotton_China", 'zce_cotton.json'),
}

LLM_URL = "https://unscotched-devon-interpapillary.ngrok-free.dev/generate"

def call_llm(system_prompt, user_query):
    try:
        payload = {
            "system_prompt": system_prompt,
            "query": user_query,
            "max_new_tokens": 2000
        }
        response = requests.post(LLM_URL, json=payload, timeout=240)
        if response.status_code == 200:
            return response.json()["response"]
        return f"LLM Error: {response.text}"
    except Exception as e:
        return f"LLM Connection Error: {e}"

# ── Helpers ─────────────────────────────────────────────────────────────────

def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"  WARN: Could not load {path}: {e}")
        return None

def load_csv(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    except Exception as e:
        print(f"  WARN: Could not load {path}: {e}")
        return None

def parse_number(val):
    """Robustly extract a float from any value - numbers, currency strings, etc."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    # Remove common prefixes/suffixes
    s = s.replace("Rs.", "").replace("Rs", "").replace("PKR", "")
    s = s.replace("US$", "").replace("USD", "").replace("$", "")
    s = s.replace("CNY", "").replace("/KG", "").replace("/kg", "")
    s = s.replace(",", "")  # thousands separator
    s = s.strip().rstrip("s")  # trailing 's' from barchart
    # Remove +/- Gst text
    s = re.sub(r'\+\s*Gst', '', s, flags=re.IGNORECASE).strip()
    try:
        return float(s)
    except ValueError:
        # Try extracting first number
        m = re.search(r'[-+]?[\d.]+', s)
        return float(m.group()) if m else None

def parse_pct(s):
    """Extract percentage value from strings like '+2.05%', '(-0.26%)', '-3% down'."""
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    m = re.search(r'([+-]?\d+\.?\d*)\s*%', str(s))
    if m:
        return float(m.group(1))
    # Try without % sign  
    m = re.search(r'[+-]?\d+\.?\d*', str(s))
    return float(m.group()) if m else None

def alert(rule_id, category, rule_name, condition, triggered, severity, recommendation, data_used):
    return {
        "rule_id": rule_id,
        "category": category,
        "rule_name": rule_name,
        "condition": condition,
        "triggered": triggered,
        "severity": severity,
        "recommendation": recommendation,
        "data_used": data_used,
    }

# ── Data loader ─────────────────────────────────────────────────────────────

def load_all_data():
    d = {}
    for key, path in DATA_FILES.items():
        if path.endswith(".csv"):
            d[key] = load_csv(path)
        else:
            d[key] = load_json(path)
    return d

# ═══════════════════════════════════════════════════════════════════════════
#  EXTRACTED VALUES — Central data extraction with debug printing
# ═══════════════════════════════════════════════════════════════════════════

def extract_all_values(data):
    """Extract and validate all values from JSONs into a flat dict for rules."""
    v = {}

    # ── 1. Brent Oil: brent_oil.json ──
    # Structure: {"current_value": 71.02, "previous_close": 70.77, "absolute_change": -0.19, "relative_change": "-0.27%"}
    brent = data.get("brent_oil") or {}
    v["brent_price"] = parse_number(brent.get("current_value"))
    v["brent_prev"] = parse_number(brent.get("previous_close"))
    v["brent_change"] = parse_number(brent.get("absolute_change"))
    v["brent_change_pct"] = parse_pct(brent.get("relative_change"))

    # ── 2. China Yarn: yarn_index_china.json ──
    # Structure: {"last_price": "21,330.00", "price_change": "+730.00", "percent_change": "(+3.54%)"}
    cy = data.get("china_yarn") or {}
    v["china_yarn_price"] = parse_number(cy.get("last_price"))
    v["china_yarn_change"] = parse_number(cy.get("price_change"))
    v["china_yarn_change_pct"] = parse_pct(cy.get("percent_change"))
    v["china_yarn_52wk_low"] = parse_number(cy.get("week52_range_low"))
    v["china_yarn_52wk_high"] = parse_number(cy.get("week52_range_high"))

    # ── 3. Cotlook A Index: cotlook_a_index.json ──
    # Structure: array of {date, value}. Monthly data starts after metadata rows.
    # Monthly entries: {"date": "January 31, 2026", "value": 1.642}
    # Metadata entries: {"date": "Last Value", "value": 1.642}
    cotlook = data.get("cotlook_a") or []
    v["cotlook_a_latest"] = None
    v["cotlook_a_date"] = None
    v["cotlook_a_prev_month"] = None
    for entry in cotlook:
        d_str = entry.get("date", "")
        val = entry.get("value")
        if isinstance(val, (int, float)) and re.match(r'^[A-Z][a-z]+ \d+, \d{4}$', d_str):
            if v["cotlook_a_latest"] is None:
                v["cotlook_a_latest"] = float(val)
                v["cotlook_a_date"] = d_str
            elif v["cotlook_a_prev_month"] is None:
                v["cotlook_a_prev_month"] = float(val)
                break  # Got both latest and previous

    # ── 4. ICE Cotton Global: cotton_prices.json ──
    # Structure: {"current_value": "0.65", "previous_close": "0.64", "relative_change": "1.95%"}
    # Values are in USD per pound (cents)
    cg = data.get("cotton_global") or {}
    v["ice_cotton_price"] = parse_number(cg.get("current_value"))
    v["ice_cotton_prev"] = parse_number(cg.get("previous_close"))
    v["ice_cotton_change_pct"] = parse_pct(cg.get("relative_change"))

    # ── 5. Cotton Pakistan: cotton_pakistan.json ──
    # Structure: {"extracted_prices": {"price_min_per_40kg_pkr": 7350, "price_max_per_40kg_pkr": 9800, "price_per_kg_pkr": 245}}
    cpk = data.get("cotton_pakistan") or {}
    prices = cpk.get("extracted_prices") or {}
    v["pk_cotton_min_40kg"] = parse_number(prices.get("price_min_per_40kg_pkr"))
    v["pk_cotton_max_40kg"] = parse_number(prices.get("price_max_per_40kg_pkr"))
    v["pk_cotton_per_kg"] = parse_number(prices.get("price_per_kg_pkr"))

    # ── 6. Forex: forex_data.json ──
    # Structure: {investing_pairs: {USD_PKR: {last_price, change, percent_change}}, 
    #             open_market: {USD_PKR: {buying, selling}}, 
    #             pakistan_indicators: {interest_rate: {value}, foreign_exchange_reserves: {value, previous}},
    #             kibid_kibor: {KIBID_6M: {latest_value}, KIBOR_6M: {latest_value}},
    #             usdpkr_forwards: [{name, bid, ask}]}
    fx = data.get("forex") or {}
    pairs = fx.get("investing_pairs") or {}
    omkt = fx.get("open_market") or {}
    indic = fx.get("pakistan_indicators") or {}
    kibor = fx.get("kibid_kibor") or {}

    v["usd_pkr"] = parse_number((pairs.get("USD_PKR") or {}).get("last_price"))
    v["usd_pkr_change_pct"] = parse_pct((pairs.get("USD_PKR") or {}).get("percent_change"))
    v["eur_pkr"] = parse_number((pairs.get("EUR_PKR") or {}).get("last_price"))
    v["eur_usd"] = parse_number((pairs.get("EUR_USD") or {}).get("last_price"))
    v["cny_pkr"] = parse_number((pairs.get("CNY_PKR") or {}).get("last_price"))

    v["open_usd_buy"] = parse_number((omkt.get("USD_PKR") or {}).get("buying"))
    v["open_usd_sell"] = parse_number((omkt.get("USD_PKR") or {}).get("selling"))
    v["open_eur_buy"] = parse_number((omkt.get("EUR_PKR") or {}).get("buying"))
    v["open_gbp_buy"] = parse_number((omkt.get("GBP_PKR") or {}).get("buying"))

    v["pk_interest_rate"] = parse_number((indic.get("interest_rate") or {}).get("value"))
    v["pk_interbank_rate"] = parse_number((indic.get("interbank_rate") or {}).get("value"))
    v["fx_reserves"] = parse_number((indic.get("foreign_exchange_reserves") or {}).get("value"))
    v["fx_reserves_prev"] = parse_number((indic.get("foreign_exchange_reserves") or {}).get("previous"))
    v["fx_reserves_date"] = (indic.get("foreign_exchange_reserves") or {}).get("date")

    v["kibor_6m"] = parse_number((kibor.get("KIBOR_6M") or {}).get("latest_value"))
    v["kibid_6m"] = parse_number((kibor.get("KIBID_6M") or {}).get("latest_value"))
    v["kibor_date"] = (kibor.get("KIBOR_6M") or {}).get("latest_date")

    # Forward rates
    forwards = fx.get("usdpkr_forwards") or []
    v["fwd_1m_bid"] = None
    v["fwd_3m_bid"] = None
    v["fwd_6m_bid"] = None
    for fwd in forwards:
        if not isinstance(fwd, dict):
            continue
        name = fwd.get("name", "")
        if "1M FWD" in name and "1" in name:
            v["fwd_1m_bid"] = parse_number(fwd.get("bid"))
        if "3M FWD" in name:
            v["fwd_3m_bid"] = parse_number(fwd.get("bid"))
        if "6M FWD" in name:
            v["fwd_6m_bid"] = parse_number(fwd.get("bid"))

    # ── 7. Glycol/TPA: glycol_terephthalic.json ──
    # Structure: {terephthalic_acid: {regions: [{region, price, change}]}, ethylene_glycol: {regions: [...]}}
    gt = data.get("glycol_tpa") or {}
    v["tpa_regions"] = (gt.get("terephthalic_acid") or {}).get("regions") or []
    v["eg_regions"] = (gt.get("ethylene_glycol") or {}).get("regions") or []

    # ── 8. Naphthapreis: naphthapreis.json ──
    # Structure: {"current_value": 563.24, "absolute_change": 0.74, "relative_change": "0.13%"}
    nap = data.get("naphthapreis") or {}
    v["naphtha_price"] = parse_number(nap.get("current_value"))
    v["naphtha_change"] = parse_number(nap.get("absolute_change"))
    v["naphtha_change_pct"] = parse_pct(nap.get("relative_change"))

    # ── 9. ZCE Cotton China: zce_cotton.json ──
    # Structure: {"last_price_raw": 15400, "price_change_raw": 310, "percent_change_raw": 2.05, "percent_change": "+2.05%"}
    zce = data.get("zce_cotton") or {}
    v["zce_cotton_price"] = parse_number(zce.get("last_price_raw")) or parse_number(zce.get("last_price"))
    v["zce_cotton_change"] = parse_number(zce.get("price_change_raw")) or parse_number(zce.get("price_change"))
    v["zce_cotton_change_pct"] = parse_number(zce.get("percent_change_raw")) or parse_pct(zce.get("percent_change"))

    # ── 10. Yarn Pakistan: yarn_prices.json ──
    # Structure: {"20S Cotton": ["Rs. 3230", ...], "30S Cotton": [...], "40 CF Cotton": [...], "60 CF Cotton": [...]}
    yp = data.get("yarn_pakistan") or {}
    def avg_yarn(key):
        rates = yp.get(key) or []
        if not rates:
            return None
        vals = [parse_number(r) for r in rates]
        vals = [x for x in vals if x is not None and x > 0]
        return sum(vals) / len(vals) if vals else None
    
    v["yarn_20s_avg"] = avg_yarn("20S Cotton")
    v["yarn_30s_avg"] = avg_yarn("30S Cotton")
    v["yarn_40cf_avg"] = avg_yarn("40 CF Cotton")
    v["yarn_60cf_avg"] = avg_yarn("60 CF Cotton")
    v["yarn_20s_list"] = yp.get("20S Cotton") or []
    v["yarn_30s_list"] = yp.get("30S Cotton") or []

    # ── 11. Weather: CSV ──
    weather = data.get("weather") or []
    sindh = {"Sanghar", "Hyderabad", "Ghotki", "Khairpur"}
    punjab = {"Bahawalpur", "Multan", "Rahim Yar Khan", "Khanewal", "Bahawalnagar", "Lodhran"}
    
    def safe_float(val, default=0.0):
        try:
            return float(val) if str(val).strip() else default
        except (ValueError, TypeError):
            return default
            
    v["sindh_total_rain"] = sum(safe_float(r.get("Rain Amount (mm)")) for r in weather if r.get("City") in sindh)
    v["punjab_total_rain"] = sum(safe_float(r.get("Rain Amount (mm)")) for r in weather if r.get("City") in punjab)
    v["sindh_max_rain_chance"] = max((int(safe_float(r.get("Rain Chance (%)"))) for r in weather if r.get("City") in sindh), default=0)
    v["punjab_max_rain_chance"] = max((int(safe_float(r.get("Rain Chance (%)"))) for r in weather if r.get("City") in punjab), default=0)
    v["sindh_max_temp"] = max((safe_float(r.get("Max Temp (°C)")) for r in weather if r.get("City") in sindh), default=0)
    v["punjab_max_temp"] = max((safe_float(r.get("Max Temp (°C)")) for r in weather if r.get("City") in punjab), default=0)

    return v


def print_extracted_values(v):
    """Print all extracted values for debugging."""
    print("\n" + "=" * 60)
    print("  EXTRACTED DATA VALUES (DEBUG)")
    print("=" * 60)
    sections = {
        "Brent Oil": ["brent_price", "brent_prev", "brent_change", "brent_change_pct"],
        "ICE Cotton (NY)": ["ice_cotton_price", "ice_cotton_prev", "ice_cotton_change_pct"],
        "ZCE Cotton (China)": ["zce_cotton_price", "zce_cotton_change", "zce_cotton_change_pct"],
        "Cotlook A Index": ["cotlook_a_latest", "cotlook_a_date", "cotlook_a_prev_month"],
        "Cotton Pakistan": ["pk_cotton_min_40kg", "pk_cotton_max_40kg", "pk_cotton_per_kg"],
        "China Yarn": ["china_yarn_price", "china_yarn_change_pct"],
        "Yarn Pakistan Avg": ["yarn_20s_avg", "yarn_30s_avg", "yarn_40cf_avg", "yarn_60cf_avg"],
        "Naphtha": ["naphtha_price", "naphtha_change", "naphtha_change_pct"],
        "USD/PKR": ["usd_pkr", "usd_pkr_change_pct", "open_usd_buy", "open_usd_sell"],
        "EUR/USD": ["eur_usd"],
        "CNY/PKR": ["cny_pkr"],
        "Pakistan Rates": ["pk_interest_rate", "pk_interbank_rate", "kibor_6m", "kibid_6m"],
        "FX Reserves": ["fx_reserves", "fx_reserves_prev", "fx_reserves_date"],
        "Forwards": ["fwd_1m_bid", "fwd_3m_bid", "fwd_6m_bid"],
        "Weather Sindh": ["sindh_total_rain", "sindh_max_rain_chance", "sindh_max_temp"],
        "Weather Punjab": ["punjab_total_rain", "punjab_max_rain_chance", "punjab_max_temp"],
    }
    for section, keys in sections.items():
        vals = "  |  ".join(f"{k}={v.get(k)}" for k in keys)
        print(f"  {section}: {vals}")
    print("=" * 60)


# ═══════════════════════════════════════════════════════════════════════════
#  RULE ENGINE
# ═══════════════════════════════════════════════════════════════════════════

def evaluate_all_rules(v, data):
    """Evaluate all business rules using extracted values."""
    alerts = []
    now = datetime.now()

    # ═══════════════════════════════════════════════
    # CATEGORY A: COTTON PROCUREMENT
    # ═══════════════════════════════════════════════

    # A1: Rainy Harvest — Sindh rainfall > 50mm
    if v["sindh_total_rain"] is not None:
        t = v["sindh_total_rain"] > 50 or v["sindh_max_rain_chance"] > 60
        alerts.append(alert("A1", "Cotton Procurement", "Rainy Harvest Rule",
            f"Sindh rain={v['sindh_total_rain']:.1f}mm, max chance={v['sindh_max_rain_chance']}%",
            t, "CRITICAL" if t else "LOW",
            "Buy 3 months cotton immediately; quality will drop, prices will rise." if t
            else "No rain risk in Sindh. Normal procurement.",
            {"sindh_rain_mm": v["sindh_total_rain"], "max_chance": v["sindh_max_rain_chance"]}))

    # A3: Import Parity — Local > (Cotlook A + Freight + 11% Duty)
    if v["cotlook_a_latest"] and v["pk_cotton_per_kg"] and v["usd_pkr"]:
        local_usd = v["pk_cotton_per_kg"] / v["usd_pkr"]
        import_parity = v["cotlook_a_latest"] * 1.11 + 0.05
        t = local_usd > import_parity
        alerts.append(alert("A3", "Cotton Procurement", "Import Parity Switch",
            f"Local=${local_usd:.3f}/kg vs Import=${import_parity:.3f}/kg (Cotlook={v['cotlook_a_latest']})",
            t, "HIGH" if t else "MEDIUM",
            "Stop local buying; open LC for West African or US Cotton." if t
            else "Local cotton competitive vs imports.",
            {"local_usd_kg": round(local_usd, 3), "import_parity_usd_kg": round(import_parity, 3),
             "cotlook_a": v["cotlook_a_latest"], "pk_per_kg": v["pk_cotton_per_kg"], "usd_pkr": v["usd_pkr"]}))

    # A4: China Future Link — ZCE Cotton > +3%
    if v["zce_cotton_change_pct"] is not None:
        t = v["zce_cotton_change_pct"] > 3
        alerts.append(alert("A4", "Cotton Procurement", "China Future Link",
            f"ZCE Cotton change={v['zce_cotton_change_pct']:+.2f}% (threshold: >+3%)",
            t, "CRITICAL" if t else "LOW",
            "Buy local spot cotton within 2 hours; local follows China with a lag." if t
            else "ZCE futures normal. No urgency.",
            {"zce_change_pct": v["zce_cotton_change_pct"], "zce_price": v["zce_cotton_price"]}))

    # A6: NY Futures Dip — ICE < 80 cents/lb
    if v["ice_cotton_price"] is not None:
        t = v["ice_cotton_price"] < 0.80
        alerts.append(alert("A6", "Cotton Procurement", "NY Futures Dip",
            f"ICE Cotton=${v['ice_cotton_price']:.2f}/lb (threshold: <$0.80)",
            t, "HIGH" if t else "LOW",
            "Lock prices for 6 months of imported cotton at this dip." if t
            else "ICE Cotton above 80 cents.",
            {"ice_price": v["ice_cotton_price"]}))

    # A10: Spinning Margin Squeeze — Cotton rising + Yarn flat
    if v["ice_cotton_change_pct"] is not None:
        t = v["ice_cotton_change_pct"] > 1.5
        alerts.append(alert("A10", "Cotton Procurement", "Spinning Margin Squeeze",
            f"Cotton up {v['ice_cotton_change_pct']:.1f}% (threshold: >1.5%)",
            t, "HIGH" if t else "LOW",
            "Spinners will stop selling -> Secure yarn stocks before supply dries up." if t
            else "Spinning margins stable.",
            {"cotton_change_pct": v["ice_cotton_change_pct"]}))

    # A2: Cotlook A Momentum — MoM change signals import timing
    if v["cotlook_a_latest"] and v["cotlook_a_prev_month"] and v["cotlook_a_prev_month"] > 0:
        mom = ((v["cotlook_a_latest"] - v["cotlook_a_prev_month"]) / v["cotlook_a_prev_month"]) * 100
        t = abs(mom) > 5
        rec = ("Cotlook A fell sharply — buy opportunity before rebound. Open LC now." if mom < -5
               else "Cotlook A surging — delay imports, buy local spot instead." if mom > 5
               else "Cotlook A stable month-over-month.")
        alerts.append(alert("A2", "Cotton Procurement", "Cotlook A Momentum",
            f"Latest={v['cotlook_a_latest']}, Prev={v['cotlook_a_prev_month']}, MoM={mom:+.1f}%",
            t, "HIGH" if t else "LOW", rec,
            {"latest": v["cotlook_a_latest"], "prev_month": v["cotlook_a_prev_month"], "mom_pct": round(mom, 1)}))

    # A5: Pakistan Cotton Price Spread — quality uncertainty
    if v["pk_cotton_min_40kg"] and v["pk_cotton_max_40kg"] and v["pk_cotton_min_40kg"] > 0:
        spread = ((v["pk_cotton_max_40kg"] - v["pk_cotton_min_40kg"]) / v["pk_cotton_min_40kg"]) * 100
        t = spread > 30
        alerts.append(alert("A5", "Cotton Procurement", "Pakistan Cotton Price Spread",
            f"Min=Rs.{v['pk_cotton_min_40kg']:.0f}, Max=Rs.{v['pk_cotton_max_40kg']:.0f}/40kg, spread={spread:.1f}%",
            t, "MEDIUM" if t else "LOW",
            "Wide band signals quality uncertainty — demand grading certificates before bulk purchase." if t
            else f"Spread {spread:.1f}% normal. Market consistent.",
            {"min_40kg": v["pk_cotton_min_40kg"], "max_40kg": v["pk_cotton_max_40kg"], "spread_pct": round(spread, 1)}))

    # A7: Cotton Crop Season Alert — Pakistan calendar pressure points
    kharif   = now.month in [4, 5, 6]    # sowing: price firms
    ginning  = now.month in [9, 10, 11]  # supply peak: prices soften
    tight    = now.month in [12, 1, 2, 3] # stocks deplete: prices firm
    season   = ("Kharif Sowing" if kharif else "Ginning Season" if ginning
                else "Tight Supply Window" if tight else "Off-Season")
    rec_s    = ("New crop uncertainty — lock 3-month forward cotton contracts." if kharif
                else "Peak supply — negotiate hard; prices at seasonal floor." if ginning
                else "Stocks depleting — build 90-day safety buffer immediately." if tight
                else "Monitor sowing intentions for next cycle.")
    alerts.append(alert("A7", "Cotton Procurement", "Crop Season Calendar Alert",
        f"Season: {season} (Month={now.strftime('%B')})",
        kharif or tight, "MEDIUM" if (kharif or tight) else "INFO", rec_s,
        {"season": season, "month": now.strftime("%B %Y")}))

    # ═══════════════════════════════════════════════
    # CATEGORY B: YARN BUYING STRATEGY
    # ═══════════════════════════════════════════════

    # B1: Count Spread Arbitrage — 30s vs 40s gap < 5%
    if v["yarn_30s_avg"] and v["yarn_40cf_avg"] and v["yarn_30s_avg"] > 0:
        gap = ((v["yarn_40cf_avg"] - v["yarn_30s_avg"]) / v["yarn_30s_avg"]) * 100
        t = gap < 5
        alerts.append(alert("B1", "Yarn Strategy", "Count Spread Arbitrage",
            f"30s=Rs.{v['yarn_30s_avg']:.0f}, 40CF=Rs.{v['yarn_40cf_avg']:.0f}, gap={gap:.1f}% (<5%?)",
            t, "MEDIUM" if t else "LOW",
            "Buy 40s yarn; gap is artificially low and will correct upwards." if t
            else f"Count spread {gap:.1f}% is normal.",
            {"yarn_30s": round(v["yarn_30s_avg"]), "yarn_40cf": round(v["yarn_40cf_avg"]), "gap_pct": round(gap, 1)}))

    # B3: Polyester Oil Link — Brent > $90
    if v["brent_price"] is not None:
        t = v["brent_price"] > 90
        alerts.append(alert("B3", "Yarn Strategy", "Polyester Oil Link",
            f"Brent=${v['brent_price']:.2f} (threshold: >$90)",
            t, "HIGH" if t else "LOW",
            "Buy PC yarn today; PSF tracks oil with 2-week lag." if t
            else f"Brent at ${v['brent_price']:.2f}. Polyester stable.",
            {"brent": v["brent_price"]}))

    # B4: Carded vs Combed Gap — premium > 25%
    if v["yarn_20s_avg"] and v["yarn_60cf_avg"] and v["yarn_20s_avg"] > 0:
        premium = ((v["yarn_60cf_avg"] - v["yarn_20s_avg"]) / v["yarn_20s_avg"]) * 100
        t = premium > 25
        alerts.append(alert("B4", "Yarn Strategy", "Carded vs Combed Gap",
            f"20S(Carded)=Rs.{v['yarn_20s_avg']:.0f}, 60CF(Combed)=Rs.{v['yarn_60cf_avg']:.0f}, premium={premium:.1f}%",
            t, "MEDIUM" if t else "LOW",
            "Switch to 'Carded Compact' if client approves; combed premium too high." if t
            else "Combed premium acceptable.",
            {"yarn_20s": round(v["yarn_20s_avg"]), "yarn_60cf": round(v["yarn_60cf_avg"]), "premium": round(premium, 1)}))

    # B11: Fine Count Season — Jan-Mar EU summer prep
    t = now.month in [1, 2, 3]
    alerts.append(alert("B11", "Yarn Strategy", "Fine Count Season",
        f"Month={now.strftime('%B')} (EU prep: Jan-Mar)",
        t, "MEDIUM" if t else "LOW",
        "Demand for 60s/80s Lawn yarn spiking -> Pre-book fine counts." if t
        else "Outside EU summer prep window.",
        {"month": now.strftime("%B %Y")}))

    # B_CHINA: China Yarn Futures > 3% change
    if v["china_yarn_change_pct"] is not None:
        t = abs(v["china_yarn_change_pct"]) > 3
        alerts.append(alert("B_CHINA", "Yarn Strategy", "China Yarn Futures Alert",
            f"ZCE Yarn change={v['china_yarn_change_pct']:+.2f}% (threshold: >|3%|)",
            t, "HIGH" if t else "LOW",
            "Significant ZCE yarn movement. Local yarn prices will follow." if t
            else "ZCE yarn futures normal.",
            {"price": v["china_yarn_price"], "change_pct": v["china_yarn_change_pct"]}))

    # B2: Spinner Profitability Squeeze — if spinners losing money, supply will tighten
    if v["yarn_20s_avg"] and v["pk_cotton_per_kg"]:
        # ~1.15kg raw cotton needed per kg yarn (waste+twist)
        cotton_equiv = v["pk_cotton_per_kg"] * 1.15 * 10  # per 10kg lot
        margin_pct   = ((v["yarn_20s_avg"] - cotton_equiv) / cotton_equiv) * 100
        t = margin_pct < 10
        alerts.append(alert("B2", "Yarn Strategy", "Spinner Profitability Squeeze",
            f"20s=Rs.{v['yarn_20s_avg']:.0f}, Cotton cost=Rs.{cotton_equiv:.0f}/10kg, margin={margin_pct:.1f}%",
            t, "HIGH" if t else "LOW",
            f"Spinners at {margin_pct:.0f}% margin — production cuts coming. Buy yarn immediately before shortage." if t
            else f"Spinners healthy at {margin_pct:.0f}% margin. Yarn supply stable.",
            {"yarn_20s": round(v["yarn_20s_avg"]), "cotton_cost": round(cotton_equiv), "margin_pct": round(margin_pct, 1)}))

    # B5: 20s-to-30s Upgrade Opportunity — when premium is negligible
    if v["yarn_20s_avg"] and v["yarn_30s_avg"] and v["yarn_20s_avg"] > 0:
        upgrade_cost = ((v["yarn_30s_avg"] - v["yarn_20s_avg"]) / v["yarn_20s_avg"]) * 100
        t = upgrade_cost < 10
        alerts.append(alert("B5", "Yarn Strategy", "20s-to-30s Upgrade Opportunity",
            f"20s=Rs.{v['yarn_20s_avg']:.0f}, 30s=Rs.{v['yarn_30s_avg']:.0f}, upgrade={upgrade_cost:.1f}%",
            t, "MEDIUM" if t else "LOW",
            "Upgrade to 30s for near-zero premium — better client quality, improved margins." if t
            else f"30s commands {upgrade_cost:.1f}% premium. Upgrade not cost-justified.",
            {"yarn_20s": round(v["yarn_20s_avg"]), "yarn_30s": round(v["yarn_30s_avg"]), "upgrade_pct": round(upgrade_cost, 1)}))

    # B6: China Yarn Near 52-Week High — dangerous entry point
    if v["china_yarn_price"] and v["china_yarn_52wk_high"] and v["china_yarn_52wk_high"] > 0:
        pct_of_high = (v["china_yarn_price"] / v["china_yarn_52wk_high"]) * 100
        t = pct_of_high > 95
        alerts.append(alert("B6", "Yarn Strategy", "China Yarn Near 52-Week High",
            f"ZCE Yarn={v['china_yarn_price']:.0f}, 52wk High={v['china_yarn_52wk_high']:.0f}, at {pct_of_high:.1f}% of peak",
            t, "HIGH" if t else "LOW",
            "ZCE yarn near 52wk high — DO NOT buy China yarn now; await 5-10% correction." if t
            else f"ZCE yarn at {pct_of_high:.1f}% of 52wk high. Reasonable entry.",
            {"price": v["china_yarn_price"], "52wk_high": v["china_yarn_52wk_high"], "pct_of_high": round(pct_of_high, 1)}))

    # ═══════════════════════════════════════════════
    # CATEGORY C: CHEMICALS & DYES
    # ═══════════════════════════════════════════════

    # C1: Reactive Dye Crude Link — Naphtha rising
    if v["naphtha_price"] is not None:
        t = (v["naphtha_change"] or 0) > 0 and v["naphtha_price"] > 550
        alerts.append(alert("C1", "Chemicals & Dyes", "Reactive Dye Crude Link",
            f"Naphtha=${v['naphtha_price']:.0f}/ton, change={v['naphtha_change']:+.2f}",
            t, "HIGH" if t else "LOW",
            "Naphtha rising -> Reactive dyes will get expensive. Stock up." if t
            else "Naphtha stable. Dye costs under control.",
            {"naphtha_price": v["naphtha_price"], "naphtha_change": v["naphtha_change"]}))

    # C_TPA/EG: Regional chemical alerts
    for chem_key, chem_name, regions_key in [("TPA", "Terephthalic Acid", "tpa_regions"), 
                                               ("EG", "Ethylene Glycol", "eg_regions")]:
        for rd in v.get(regions_key, []):
            change_str = rd.get("change", "")
            is_rising = "up" in change_str.lower()
            change_val = parse_pct(change_str)
            if is_rising and change_val and change_val > 2:
                region = rd.get("region", "Unknown")
                alerts.append(alert(
                    f"C_{chem_key}_{region.replace(' ','_')}", "Chemicals & Dyes",
                    f"{chem_name} Rising ({region})",
                    f"{chem_name} {region}={rd.get('price','?')}, {change_str}",
                    True, "MEDIUM",
                    f"{chem_name} rising in {region}. Stock up on inputs.",
                    {"chemical": chem_name, "region": region, "price": rd.get("price"), "change": change_str}))

    # C2: Naphtha Surge — >5% change signals dye cost shift in 3-4 weeks
    if v["naphtha_change_pct"] is not None:
        t = abs(v["naphtha_change_pct"]) > 5
        direction = "surging" if (v["naphtha_change_pct"] or 0) > 0 else "crashing"
        alerts.append(alert("C2", "Chemicals & Dyes", "Naphtha Surge/Crash Alert",
            f"Naphtha change={v['naphtha_change_pct']:+.1f}% (threshold: >|5%|)",
            t, "HIGH" if t else "LOW",
            f"Naphtha {direction} — dye costs shift in 3-4 weeks. {'Lock dye stocks now.' if (v['naphtha_change_pct'] or 0) > 0 else 'Delay dye purchases 2-3 weeks for savings.'}" if t
            else "Naphtha stable. Dye cost outlook predictable.",
            {"naphtha_pct_change": v["naphtha_change_pct"], "naphtha_price": v["naphtha_price"]}))

    # C3: Polyester Input Compound Risk — both TPA AND EG rising
    tpa_r = any("up" in str(r.get("change","")).lower() and (parse_pct(r.get("change","")) or 0) > 3
                for r in v.get("tpa_regions", []))
    eg_r  = any("up" in str(r.get("change","")).lower() and (parse_pct(r.get("change","")) or 0) > 3
                for r in v.get("eg_regions", []))
    t_c3  = tpa_r and eg_r
    alerts.append(alert("C3", "Chemicals & Dyes", "Polyester Input Compound Risk",
        f"TPA rising: {tpa_r}, EG rising: {eg_r} — both pressured simultaneously",
        t_c3, "CRITICAL" if t_c3 else ("MEDIUM" if (tpa_r or eg_r) else "LOW"),
        "BOTH TPA & EG rising — polyester yarn/fabric cost spike 8-12% in 4 weeks. Lock polyester contracts immediately." if t_c3
        else ("One polyester input rising — consider partial forward cover." if (tpa_r or eg_r)
              else "Polyester inputs stable."),
        {"tpa_rising": tpa_r, "eg_rising": eg_r}))

    # ═══════════════════════════════════════════════
    # CATEGORY D: CURRENCY & FOREX
    # ═══════════════════════════════════════════════

    # D2: Import Payment Timing — USD/PKR volatile
    if v["usd_pkr"] and v["usd_pkr_change_pct"] is not None:
        t = abs(v["usd_pkr_change_pct"]) > 0.5
        alerts.append(alert("D2", "Currency & Forex", "Import Payment Timing",
            f"USD/PKR change={v['usd_pkr_change_pct']:+.2f}% (volatile >±0.5%)",
            t, "HIGH" if t else "LOW",
            "Book Forward Cover to lock rate." if t
            else f"USD/PKR stable at {v['usd_pkr']}.",
            {"usd_pkr": v["usd_pkr"], "change_pct": v["usd_pkr_change_pct"]}))

    # D3: Euro/Dollar Cross — EUR/USD < 1.05
    if v["eur_usd"] is not None:
        t = v["eur_usd"] < 1.05
        alerts.append(alert("D3", "Currency & Forex", "Euro Dollar Cross",
            f"EUR/USD={v['eur_usd']:.4f} (threshold: <1.05)",
            t, "HIGH" if t else "LOW",
            "Invoice EU clients in USD; Euro too weak." if t
            else f"EUR/USD at {v['eur_usd']:.4f}. Euro healthy.",
            {"eur_usd": v["eur_usd"]}))

    # D4: Interest Rate Carry — PKR > 20%
    if v["pk_interest_rate"] is not None:
        t = v["pk_interest_rate"] > 20
        alerts.append(alert("D4", "Currency & Forex", "Interest Rate Carry",
            f"PKR rate={v['pk_interest_rate']}% (threshold: >20%)",
            t, "HIGH" if t else "LOW",
            "Borrow in USD (FE-25 loan) instead of PKR." if t
            else f"PKR rate at {v['pk_interest_rate']}%. PKR borrowing OK.",
            {"pk_rate": v["pk_interest_rate"]}))

    # D5: RMB Payment Option
    if v["cny_pkr"] and v["usd_pkr"]:
        implied = v["usd_pkr"] / 7.25
        saving = ((implied - v["cny_pkr"]) / implied) * 100
        t = saving > 1
        alerts.append(alert("D5", "Currency & Forex", "RMB Payment Option",
            f"Direct CNY/PKR={v['cny_pkr']:.2f}, Implied={implied:.2f}, saving={saving:.1f}%",
            t, "MEDIUM" if t else "LOW",
            "Pay China imports in CNY to save on conversion." if t
            else "CNY not advantageous currently.",
            {"cny_pkr": v["cny_pkr"], "implied": round(implied, 2), "saving_pct": round(saving, 1)}))

    # D10: Open Market Gap — Interbank vs Open Market > 5 PKR
    if v["usd_pkr"] and v["open_usd_sell"]:
        gap = v["open_usd_sell"] - v["usd_pkr"]
        t = abs(gap) > 5
        alerts.append(alert("D10", "Currency & Forex", "Open Market Gap",
            f"Interbank={v['usd_pkr']}, Open Sell={v['open_usd_sell']}, gap={gap:.2f} (>5?)",
            t, "CRITICAL" if t else "LOW",
            "Expect crackdown or devaluation -> Hedge immediately." if t
            else f"Gap {gap:.2f} PKR. Market aligned.",
            {"interbank": v["usd_pkr"], "open_sell": v["open_usd_sell"], "gap": round(gap, 2)}))

    # D_KIBOR: Monitor
    if v["kibor_6m"] is not None:
        alerts.append(alert("D_KIBOR", "Currency & Forex", "KIBOR Monitor",
            f"6M KIBOR={v['kibor_6m']}%, KIBID={v['kibid_6m']}% ({v['kibor_date']})",
            False, "INFO",
            f"KIBOR at {v['kibor_6m']}%. Factor into carrying cost.",
            {"kibor": v["kibor_6m"], "kibid": v["kibid_6m"], "date": v["kibor_date"]}))

    # D_FWD: Forward Premium
    if v["fwd_1m_bid"] and v["usd_pkr"]:
        annual = (v["fwd_1m_bid"] / v["usd_pkr"]) * 12 * 100
        alerts.append(alert("D_FWD", "Currency & Forex", "Forward Premium Monitor",
            f"1M FWD bid={v['fwd_1m_bid']} paise, annual={annual:.1f}%",
            False, "INFO",
            f"Forward premium implies {annual:.1f}% annualized devaluation.",
            {"fwd_1m": v["fwd_1m_bid"], "annual_pct": round(annual, 1)}))

    # D6: GBP Strong — UK export invoicing advantage
    if v["open_gbp_buy"] and v["usd_pkr"]:
        implied_gbp_usd = v["open_gbp_buy"] / v["usd_pkr"]
        t = implied_gbp_usd > 1.28
        alerts.append(alert("D6", "Currency & Forex", "GBP Export Invoicing Signal",
            f"GBP buy=Rs.{v['open_gbp_buy']:.0f}, Implied GBP/USD={implied_gbp_usd:.3f} (>1.28?)",
            t, "MEDIUM" if t else "LOW",
            "GBP strong — invoice UK buyers in GBP for better realization." if t
            else f"GBP/USD at {implied_gbp_usd:.3f}. Invoice in USD standard.",
            {"gbp_buy_pkr": v["open_gbp_buy"], "implied_gbp_usd": round(implied_gbp_usd, 3)}))

    # D7: KIBOR Working Capital Cost — high rate = expensive PKR borrowing
    if v["kibor_6m"] is not None:
        t_high = v["kibor_6m"] > 15
        t_med  = v["kibor_6m"] > 10
        sev_d7 = "CRITICAL" if t_high else ("HIGH" if t_med else "LOW")
        rec_d7 = (f"KIBOR {v['kibor_6m']}% — minimize PKR inventory financing; switch to supplier credit." if t_high
                  else f"KIBOR {v['kibor_6m']}% — factor Rs.{v['kibor_6m']:.1f}/100 monthly carrying cost into pricing." if t_med
                  else f"KIBOR {v['kibor_6m']}% — borrowing cost manageable.")
        alerts.append(alert("D7", "Currency & Forex", "KIBOR Working Capital Cost",
            f"6M KIBOR={v['kibor_6m']}% (CRITICAL>15%, HIGH>10%)",
            t_high or t_med, sev_d7, rec_d7,
            {"kibor_6m": v["kibor_6m"]}))

    # D8: FX Reserves Declining Trend
    if v["fx_reserves"] and v["fx_reserves_prev"] and v["fx_reserves_prev"] > 0:
        rsv_change     = v["fx_reserves"] - v["fx_reserves_prev"]
        rsv_change_pct = (rsv_change / v["fx_reserves_prev"]) * 100
        t = rsv_change < 0 and abs(rsv_change_pct) > 3
        alerts.append(alert("D8", "Currency & Forex", "FX Reserves Declining",
            f"Reserves=${v['fx_reserves']:.0f}M, Δ={rsv_change:+.0f}M ({rsv_change_pct:+.1f}%)",
            t, "HIGH" if t else "LOW",
            f"Reserves falling {abs(rsv_change_pct):.1f}% — PKR devaluation risk rising. Expedite import payments." if t
            else "Reserves stable/growing. PKR outlook balanced.",
            {"reserves": v["fx_reserves"], "change_m": round(rsv_change), "change_pct": round(rsv_change_pct, 1)}))

    # ═══════════════════════════════════════════════
    # CATEGORY E: STRATEGIC SOURCING
    # ═══════════════════════════════════════════════

    # E3: Inventory Carrying Cost — Rate > 22%
    if v["pk_interest_rate"] is not None:
        t = v["pk_interest_rate"] > 22
        alerts.append(alert("E3", "Strategic Sourcing", "Inventory Carrying Cost",
            f"Rate={v['pk_interest_rate']}% (>22%?)",
            t, "HIGH" if t else "MEDIUM",
            "Do NOT stock 6 months; hand-to-mouth buying cheaper." if t
            else f"Rate {v['pk_interest_rate']}%. Strategic stocking OK.",
            {"rate": v["pk_interest_rate"]}))

    # E4: Supplier Credit Arbitrage
    if v["pk_interest_rate"] is not None:
        credit_cost = (2.0 / 60) * 365  # 2% for 60 days annualized = ~12.2%
        t = v["pk_interest_rate"] > credit_cost
        alerts.append(alert("E4", "Strategic Sourcing", "Supplier Credit Arbitrage",
            f"Bank={v['pk_interest_rate']}% vs Credit={credit_cost:.1f}% annualized",
            t, "MEDIUM" if t else "LOW",
            f"Take 60-day supplier credit; saves {v['pk_interest_rate'] - credit_cost:.1f}%." if t
            else "Bank financing cheaper.",
            {"bank_rate": v["pk_interest_rate"], "credit_cost": round(credit_cost, 1)}))

    # E8: Recycle Trend rPET
    if v["brent_price"] is not None:
        t = v["brent_price"] < 75
        alerts.append(alert("E8", "Strategic Sourcing", "Recycle Trend (rPET)",
            f"Brent=${v['brent_price']:.2f} (<$75 = rPET premium shrinks)",
            t, "MEDIUM" if t else "LOW",
            "rPET premium likely <10%. Switch to rPET for EU buyers." if t
            else "Oil moderate. rPET premium elevated.",
            {"brent": v["brent_price"]}))

    # E_RESERVES: FX Reserves Watch
    if v["fx_reserves"] and v["fx_reserves_prev"]:
        change = v["fx_reserves"] - v["fx_reserves_prev"]
        t = v["fx_reserves"] < 15000
        alerts.append(alert("E_RESERVES", "Strategic Sourcing", "FX Reserves Watch",
            f"Reserves=${v['fx_reserves']:.0f}M (prev=${v['fx_reserves_prev']:.0f}M, Δ={change:+.0f}M)",
            t, "CRITICAL" if t else "LOW",
            "Low reserves -> import restrictions risk. Factor 2% extra." if t
            else f"Reserves ${v['fx_reserves']:.0f}M. Adequate.",
            {"reserves": v["fx_reserves"], "prev": v["fx_reserves_prev"], "change": round(change),
             "date": v["fx_reserves_date"]}))

    # E5: USD Hedging Window — ideal when stable USD + low forward premium
    if v["usd_pkr_change_pct"] is not None and v["fwd_1m_bid"] and v["usd_pkr"]:
        fwd_ann = (v["fwd_1m_bid"] / v["usd_pkr"]) * 12 * 100
        t = abs(v["usd_pkr_change_pct"]) < 0.3 and fwd_ann < 8
        alerts.append(alert("E5", "Strategic Sourcing", "USD Hedging Window Open",
            f"USD/PKR daily={v['usd_pkr_change_pct']:+.2f}%, fwd annual={fwd_ann:.1f}% (<8%?)",
            t, "MEDIUM" if t else "LOW",
            "Ideal conditions — buy 90-day forward cover for import payments now." if t
            else "Hedging conditions not optimal. Monitor before covering.",
            {"usd_change": v["usd_pkr_change_pct"], "fwd_annual": round(fwd_ann, 1)}))

    # E6: Compound Input Cost Squeeze — oil AND cotton rising simultaneously
    oil_up    = (v.get("brent_change_pct") or 0) > 2
    cotton_up = (v.get("ice_cotton_change_pct") or 0) > 1.5
    t_e6      = oil_up and cotton_up
    alerts.append(alert("E6", "Strategic Sourcing", "Compound Input Cost Squeeze",
        f"Oil change={v.get('brent_change_pct',0):+.1f}%, Cotton change={v.get('ice_cotton_change_pct',0):+.1f}%",
        t_e6, "CRITICAL" if t_e6 else "LOW",
        "BOTH oil and cotton rising — blended fabric costs squeeze from both sides. Raise quotes 3-5% immediately." if t_e6
        else "No simultaneous oil+cotton surge.",
        {"oil_change_pct": v.get("brent_change_pct"), "cotton_change_pct": v.get("ice_cotton_change_pct")}))

    # ═══════════════════════════════════════════════
    # CATEGORY W: WEATHER RISK
    # ═══════════════════════════════════════════════

    # W1: Heat Stress Alert — tiered severity
    t_extreme = v["sindh_max_temp"] > 48 or v["punjab_max_temp"] > 48
    t_high_w1 = v["sindh_max_temp"] > 45 or v["punjab_max_temp"] > 45
    alerts.append(alert("W1", "Weather Risk", "Heat Stress Alert",
        f"Sindh max={v['sindh_max_temp']}°C, Punjab max={v['punjab_max_temp']}°C",
        t_high_w1, "CRITICAL" if t_extreme else ("HIGH" if t_high_w1 else "LOW"),
        ("EXTREME heat — cotton bolls burning; yield losses >20% likely. Source backup supply now." if t_extreme
         else "High heat — cotton quality stress; build 60-day buffer stock." if t_high_w1
         else "Temps within safe range."),
        {"sindh_temp": v["sindh_max_temp"], "punjab_temp": v["punjab_max_temp"]}))

    # W2: 16-Day Rain Forecast — tiered severity
    t_heavy_w2 = v["sindh_total_rain"] > 100 or v["punjab_total_rain"] > 100
    t_mod_w2   = v["sindh_total_rain"] > 20  or v["punjab_total_rain"] > 20
    alerts.append(alert("W2", "Weather Risk", "16-Day Rain Forecast",
        f"Sindh={v['sindh_total_rain']:.1f}mm, Punjab={v['punjab_total_rain']:.1f}mm",
        t_mod_w2, "CRITICAL" if t_heavy_w2 else ("MEDIUM" if t_mod_w2 else "LOW"),
        ("Heavy rain — field flooding risk; severe cotton quality damage." if t_heavy_w2
         else "Moderate rain — monitor crop; may delay ginning." if t_mod_w2
         else "Dry forecast. Favorable for cotton quality."),
        {"sindh_rain": v["sindh_total_rain"], "punjab_rain": v["punjab_total_rain"]}))

    # W3: Ginning Season Rain Risk — rain Sep-Nov is most damaging
    is_ginning   = now.month in [9, 10, 11]
    gin_rain_hit = is_ginning and (v["sindh_total_rain"] > 15 or v["punjab_total_rain"] > 15)
    alerts.append(alert("W3", "Weather Risk", "Ginning Season Rain Risk",
        f"Ginning season: {is_ginning}, Sindh={v['sindh_total_rain']:.1f}mm, Punjab={v['punjab_total_rain']:.1f}mm",
        gin_rain_hit, "CRITICAL" if gin_rain_hit else "LOW",
        "Rain during ginning — cotton moisture/contamination risk. Buy from mills with covers only." if gin_rain_hit
        else ("Ginning season, dry conditions — favorable quality." if is_ginning else "Outside ginning season."),
        {"ginning_season": is_ginning, "sindh_rain": v["sindh_total_rain"], "punjab_rain": v["punjab_total_rain"]}))

    # W4: Sowing Season Heat Risk — poor germination Apr-Jun >42°C
    is_sowing    = now.month in [4, 5, 6]
    sow_heat_hit = is_sowing and (v["sindh_max_temp"] > 42 or v["punjab_max_temp"] > 42)
    alerts.append(alert("W4", "Weather Risk", "Sowing Season Heat Risk",
        f"Sowing season: {is_sowing}, Sindh={v['sindh_max_temp']}°C, Punjab={v['punjab_max_temp']}°C",
        sow_heat_hit, "HIGH" if sow_heat_hit else "LOW",
        "Heat >42°C during sowing — poor germination; new crop yield at risk. Build 3-month safety stock." if sow_heat_hit
        else ("Sowing season, acceptable temps." if is_sowing else "Outside sowing season."),
        {"sowing_season": is_sowing, "sindh_temp": v["sindh_max_temp"], "punjab_temp": v["punjab_max_temp"]}))

    # W5: Dual-Belt Rain — both Sindh AND Punjab hit simultaneously
    dual_rain = v["sindh_total_rain"] > 15 and v["punjab_total_rain"] > 15
    alerts.append(alert("W5", "Weather Risk", "Dual Belt Rain Alert",
        f"Sindh={v['sindh_total_rain']:.1f}mm AND Punjab={v['punjab_total_rain']:.1f}mm both hit",
        dual_rain, "CRITICAL" if dual_rain else "LOW",
        "Both cotton belts hit — Pakistan-wide supply disruption likely. Activate import contingency plan." if dual_rain
        else "Rain limited to one belt or none. Supply from unaffected region can compensate.",
        {"sindh_rain": v["sindh_total_rain"], "punjab_rain": v["punjab_total_rain"]}))

    # ═══════════════════════════════════════════════
    # CATEGORY X: COMPOSITE / CROSS-MARKET SIGNALS
    # ═══════════════════════════════════════════════

    # X1: Perfect Storm — cotton + oil + PKR all adverse simultaneously
    x1 = [
        (v.get("ice_cotton_change_pct") or 0) > 1.0,
        (v.get("brent_change_pct") or 0) > 1.0,
        (v.get("usd_pkr_change_pct") or 0) > 0.3,
    ]
    x1_n = sum(x1)
    alerts.append(alert("X1", "Composite Risk", "Perfect Storm — All Inputs Rising",
        f"Cotton>+1%: {x1[0]}, Oil>+1%: {x1[1]}, PKR weaker>0.3%: {x1[2]} ({x1_n}/3 active)",
        x1_n >= 2, "CRITICAL" if x1_n == 3 else ("HIGH" if x1_n == 2 else "LOW"),
        ("ALL inputs moving adversely — raw material cost up 5-8% imminently. Raise quotes NOW and lock all forward contracts." if x1_n == 3
         else f"{x1_n}/3 adverse signals — elevated pressure. Partially hedge and monitor closely." if x1_n == 2
         else "No compound cost storm."),
        {"conditions_active": x1_n, "cotton_up": x1[0], "oil_up": x1[1], "pkr_weak": x1[2]}))

    # X2: Buy Window — cotton + oil + PKR all favorable simultaneously
    x2 = [
        (v.get("ice_cotton_change_pct") or 0) < -1.0,
        (v.get("brent_change_pct") or 0) < -1.0,
        abs(v.get("usd_pkr_change_pct") or 0) < 0.2,
    ]
    x2_n = sum(x2)
    alerts.append(alert("X2", "Composite Risk", "Procurement Buy Window Open",
        f"Cotton falling: {x2[0]}, Oil falling: {x2[1]}, PKR stable: {x2[2]} ({x2_n}/3 active)",
        x2_n >= 2, "HIGH" if x2_n == 3 else ("MEDIUM" if x2_n == 2 else "LOW"),
        ("IDEAL BUY WINDOW — all inputs favorable. Maximize 3-month forward purchasing across all categories." if x2_n == 3
         else "Good buying conditions — at least 2 inputs favorable. Accelerate procurement." if x2_n == 2
         else "No buy window active."),
        {"conditions_active": x2_n}))

    # X3: Export Competitiveness Surge — PKR weakening + cheap cotton
    pkr_dep   = (v.get("usd_pkr_change_pct") or 0) > 0.5
    ctn_cheap = (v.get("ice_cotton_price") or 999) < 0.80
    alerts.append(alert("X3", "Composite Risk", "Export Competitiveness Surge",
        f"PKR weakening: {pkr_dep}, Cotton cheap (<$0.80): {ctn_cheap}",
        pkr_dep and ctn_cheap, "HIGH" if (pkr_dep and ctn_cheap) else "LOW",
        "PKR weaker + cheap cotton = Pakistan textiles highly competitive. Aggressively quote export orders." if (pkr_dep and ctn_cheap)
        else "No export competitiveness surge.",
        {"pkr_depreciated": pkr_dep, "cotton_cheap": ctn_cheap}))

    return alerts


# ═══════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("  TEXBASE Risk Factor Analysis Engine")
    print("=" * 60)

    # Load raw data
    raw = load_all_data()
    
    # Extract all values with proper parsing
    v = extract_all_values(raw)
    
    # Print debug values
    print_extracted_values(v)

    # Run all rules
    print("\n[Evaluating rules...]")
    all_alerts = evaluate_all_rules(v, raw)

    # Summary
    triggered = [a for a in all_alerts if a["triggered"]]
    critical = [a for a in triggered if a["severity"] == "CRITICAL"]
    high = [a for a in triggered if a["severity"] == "HIGH"]
    medium = [a for a in triggered if a["severity"] == "MEDIUM"]

    # ── LLM Strategic Alignment ──────────────────────────────────────────────
    print("\n[Requesting LLM Strategic Analysis...]")
    system_prompt = (
        "You are a Senior Procurement Strategist at TEXBASE. Analyze the market alerts and data "
        "and output ONLY a valid JSON object (no markdown, no explanation) with these exact keys: "
        "market_overview (string), critical_actions (list of strings), cotton_dept (string), "
        "yarn_dept (string), chemicals_dept (string), forex_dept (string), "
        "14_day_watchlist (list of strings), compound_risk_score (integer 0-10)."
    )

    # Only send triggered alerts + key scalars to keep prompt concise
    snapshot_keys = ["brent_price", "brent_change_pct", "ice_cotton_price", "ice_cotton_change_pct",
                     "zce_cotton_change_pct", "cotlook_a_latest", "usd_pkr", "usd_pkr_change_pct",
                     "kibor_6m", "pk_interest_rate", "fx_reserves", "naphtha_price", "naphtha_change_pct",
                     "yarn_20s_avg", "yarn_30s_avg", "sindh_total_rain", "punjab_total_rain",
                     "sindh_max_temp", "punjab_max_temp"]
    compact_snapshot = {k: v.get(k) for k in snapshot_keys}

    user_query = f"""TRIGGERED ALERTS ({len(triggered)} active):
{json.dumps([{"id": a["rule_id"], "name": a["rule_name"], "severity": a["severity"], "rec": a["recommendation"]} for a in triggered], indent=2)}

DATA SNAPSHOT:
{json.dumps(compact_snapshot, indent=2)}

Generate the JSON object now."""
    
    llm_analysis = call_llm(system_prompt, user_query)

    output = {
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "total_rules_evaluated": len(all_alerts),
            "alerts_triggered": len(triggered),
            "critical_alerts": len(critical),
            "high_alerts": len(high),
            "medium_alerts": len(medium),
        },
        "llm_strategic_analysis": llm_analysis,
        "data_snapshot": {k: v2 for k, v2 in v.items() 
                         if not isinstance(v2, list) or len(v2) < 5},
        "triggered_alerts": sorted(triggered, key=lambda x:
            {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}.get(x["severity"], 5)),
        "all_rules": all_alerts,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=4, ensure_ascii=False)

    print(f"\n{'=' * 60}")
    print(f"  RESULTS: {len(triggered)}/{len(all_alerts)} alerts triggered")
    print(f"  CRITICAL: {len(critical)}  |  HIGH: {len(high)}  |  MEDIUM: {len(medium)}")
    print(f"{'=' * 60}")
    for a in sorted(triggered, key=lambda x: {"CRITICAL":0,"HIGH":1,"MEDIUM":2,"LOW":3}.get(x["severity"],5)):
        icon = "🔴" if a["severity"] == "CRITICAL" else "🟠" if a["severity"] == "HIGH" else "🟡"
        print(f"  {icon} [{a['severity']}] {a['rule_name']}: {a['recommendation'][:90]}")
    print(f"\nFull report -> {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
