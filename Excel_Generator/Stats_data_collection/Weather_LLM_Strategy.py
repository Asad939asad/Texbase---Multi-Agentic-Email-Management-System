#!/usr/bin/python3
"""
Weather_LLM_Strategy.py  —  TEXBASE Agricultural & Logistics Intelligence
==========================================================================
Reads the 16-day rain forecast CSV, computes rich statistics, then calls
the local LLM to produce a structured JSON strategy report.

Output → Weather_Forecast/weather_strategic_predictions.json
"""
import pandas as pd
import json
import requests
import os
from datetime import datetime

# ── Config ──────────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
CSV_PATH    = os.path.join(BASE_DIR, "Weather_Forecast", 'pakistan_16day_detailed_rain.csv')
OUTPUT_JSON = os.path.join(BASE_DIR, "Weather_Forecast", 'weather_strategic_predictions.json')
LLM_URL     = "https://unscotched-devon-interpapillary.ngrok-free.dev/generate"

SINDH_CITIES  = {"Sanghar", "Hyderabad", "Ghotki", "Khairpur"}
PUNJAB_CITIES = {"Bahawalpur", "Multan", "Rahim Yar Khan", "Khanewal", "Bahawalnagar", "Lodhran"}

# ── LLM helper ───────────────────────────────────────────────────────────────
def call_llm(system_prompt, user_query):
    try:
        r = requests.post(LLM_URL,
                          json={"system_prompt": system_prompt, "query": user_query,
                                "max_new_tokens": 2000},
                          timeout=240)
        if r.status_code == 200:
            return r.json()["response"]
        return f"LLM Error: {r.text}"
    except Exception as e:
        return f"LLM Connection Error: {e}"

# ── Data analysis helpers ────────────────────────────────────────────────────
def safe_float(val, default=0.0):
    try:
        return float(val) if str(val).strip() else default
    except (ValueError, TypeError):
        return default

def analyze_region(df, cities, region_name):
    """Compute rich statistics for a regional subset."""
    rdf = df[df["City"].isin(cities)].copy()
    if rdf.empty:
        return {"region": region_name, "no_data": True}

    rdf["Rain Amount (mm)"]   = rdf["Rain Amount (mm)"].apply(safe_float)
    rdf["Rain Chance (%)"]    = rdf["Rain Chance (%)"].apply(safe_float)
    rdf["Max Temp (°C)"]      = rdf["Max Temp (°C)"].apply(safe_float)
    rdf["Min Temp (°C)"]      = rdf["Min Temp (°C)"].apply(safe_float)
    rdf["Rain Duration (Hrs)"] = rdf["Rain Duration (Hrs)"].apply(safe_float)

    # Peak events
    peak_rain = rdf.loc[rdf["Rain Amount (mm)"].idxmax()] if len(rdf) > 0 else None
    peak_heat = rdf.loc[rdf["Max Temp (°C)"].idxmax()]   if len(rdf) > 0 else None

    # Consecutive rainy days (Rain Chance > 50%) per city
    max_consec = 0
    for city, grp in rdf.groupby("City"):
        grp = grp.sort_values("Date")
        streak = consec = 0
        for p in grp["Rain Chance (%)"]:
            if p > 50:
                consec += 1
                streak = max(streak, consec)
            else:
                consec = 0
        max_consec = max(max_consec, streak)

    # Heatwave cluster: days >= 45°C anywhere in region
    heatwave_days = int((rdf["Max Temp (°C)"] >= 45).sum())

    # Per-city summaries
    city_summaries = []
    for city, grp in rdf.groupby("City"):
        city_summaries.append({
            "city": city,
            "total_rain_mm":      round(grp["Rain Amount (mm)"].sum(), 1),
            "max_rain_chance_pct": int(grp["Rain Chance (%)"].max()),
            "max_temp_c":          round(grp["Max Temp (°C)"].max(), 1),
            "avg_temp_c":          round(grp["Max Temp (°C)"].mean(), 1),
            "total_rain_hours":    round(grp["Rain Duration (Hrs)"].sum(), 1),
        })

    return {
        "region":                region_name,
        "total_rain_mm":         round(rdf["Rain Amount (mm)"].sum(), 1),
        "max_rain_chance_pct":   int(rdf["Rain Chance (%)"].max()),
        "max_temp_c":            round(rdf["Max Temp (°C)"].max(), 1),
        "min_temp_c":            round(rdf["Min Temp (°C)"].min(), 1),
        "avg_max_temp_c":        round(rdf["Max Temp (°C)"].mean(), 1),
        "max_consec_rainy_days": max_consec,
        "heatwave_days_45plus":  heatwave_days,
        "peak_rain_event":       {"city": str(peak_rain.get("City", "")),
                                  "date": str(peak_rain.get("Date", "")),
                                  "mm":   safe_float(peak_rain.get("Rain Amount (mm)", 0))} if peak_rain is not None else None,
        "peak_heat_event":       {"city": str(peak_heat.get("City", "")),
                                  "date": str(peak_heat.get("Date", "")),
                                  "temp": safe_float(peak_heat.get("Max Temp (°C)", 0))} if peak_heat is not None else None,
        "city_summaries":        sorted(city_summaries, key=lambda x: x["total_rain_mm"], reverse=True),
    }

def get_crop_season():
    m = datetime.now().month
    if m in [4, 5, 6]:   return "Kharif Sowing (Apr-Jun) — price-sensitive"
    if m in [9, 10, 11]: return "Ginning Season (Sep-Nov) — quality-critical"
    if m in [12, 1, 2, 3]: return "Tight Supply Window (Dec-Mar)"
    return "Pre-Sowing / Off-Season"

# ── Main ─────────────────────────────────────────────────────────────────────
def generate_weather_strategies():
    if not os.path.exists(CSV_PATH):
        print(f"Error: CSV not found at {CSV_PATH}")
        return

    print(f"Reading weather data from {CSV_PATH}...")
    df = pd.read_csv(CSV_PATH)

    sindh_stats  = analyze_region(df, SINDH_CITIES,  "Sindh")
    punjab_stats = analyze_region(df, PUNJAB_CITIES, "Punjab")

    # High-risk days across all cities
    df["Rain Amount (mm)"]  = df["Rain Amount (mm)"].apply(safe_float)
    df["Rain Chance (%)"]   = df["Rain Chance (%)"].apply(safe_float)
    df["Max Temp (°C)"]     = df["Max Temp (°C)"].apply(safe_float)
    critical_days = df[(df["Rain Chance (%)"] > 60) | (df["Rain Amount (mm)"] > 15)][
        ["City", "Date", "Rain Amount (mm)", "Rain Chance (%)", "Max Temp (°C)"]
    ].to_dict(orient="records")

    summary = {
        "generated_at":     datetime.now().isoformat(),
        "forecast_period":  f"{df['Date'].min()} to {df['Date'].max()}",
        "crop_season":      get_crop_season(),
        "sindh":            sindh_stats,
        "punjab":           punjab_stats,
        "critical_days":    critical_days[:20],  # cap to avoid prompt overflow
        "cities_covered":   df["City"].unique().tolist(),
    }

    # ── LLM call ────────────────────────────────────────────────────────────
    print("Requesting Weather Strategic Analysis from LLM...")
    system_prompt = (
        "You are an expert Agricultural & Logistics Strategist for TEXBASE, a Pakistan textile company. "
        "Output ONLY a valid JSON object (no markdown, no preamble) with these exact keys: "
        "crop_risk_assessment (string: High/Medium/Low + reasoning), "
        "procurement_strategy (string: buy-now vs wait + quantities), "
        "logistics_advisory (list of city-specific warnings), "
        "operational_impacts (string: factory heat, warehouse moisture), "
        "ginning_quality_risk (string), "
        "14_day_predictions (list of date-event dicts with 'date', 'city', 'event', 'action'), "
        "overall_risk_score (integer 0-10)."
    )

    user_query = (
        f"CROP SEASON: {summary['crop_season']}\n\n"
        f"SINDH STATS:\n{json.dumps(sindh_stats, indent=2)}\n\n"
        f"PUNJAB STATS:\n{json.dumps(punjab_stats, indent=2)}\n\n"
        f"HIGH-RISK DAYS (>60% rain or >15mm):\n{json.dumps(critical_days[:10], indent=2)}\n\n"
        "Generate the JSON strategy now."
    )

    llm_raw = call_llm(system_prompt, user_query)

    # Parse JSON — strip fences if present
    try:
        clean = llm_raw.strip()
        if clean.startswith("```json"):
            clean = clean[7:].rsplit("```", 1)[0].strip()
        elif clean.startswith("```"):
            clean = clean[3:].rsplit("```", 1)[0].strip()
        strategy = json.loads(clean)
    except Exception as e:
        print(f"Warning: LLM did not return valid JSON ({e}). Storing raw.")
        strategy = {"raw_llm_response": llm_raw}

    # ── Save ─────────────────────────────────────────────────────────────────
    output = {
        "generated_at":     summary["generated_at"],
        "forecast_period":  summary["forecast_period"],
        "crop_season":      summary["crop_season"],
        "regional_stats":   {"sindh": sindh_stats, "punjab": punjab_stats},
        "critical_days":    critical_days,
        "weather_strategy": strategy,
    }

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=4, ensure_ascii=False)

    print(f"Done. Weather strategy saved → {OUTPUT_JSON}")

if __name__ == "__main__":
    generate_weather_strategies()
