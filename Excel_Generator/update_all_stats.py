#!/usr/bin/python3
"""
update_all_stats.py
===================
Orchestrator script to run all data scrapers located in the subdirectories of
Stats_data_collection, and finally run Stats.py to compute the risk factors.
"""

import os
import sys
import glob
import subprocess
import time

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATS_COLLECTION_DIR = os.path.join(BASE_DIR, "Stats_data_collection")
STATS_PY = os.path.join(STATS_COLLECTION_DIR, 'Stats.py')
WEATHER_STRAT_PY = os.path.join(STATS_COLLECTION_DIR, 'Weather_LLM_Strategy.py')

def main():
    print(f"{'═'*70}")
    print(f"  TEXBASE Global Stats Orchestrator")
    print(f"  Starting to run all scrapers in: {STATS_COLLECTION_DIR}")
    print(f"{'═'*70}\n")

    if not os.path.exists(STATS_COLLECTION_DIR):
        print(f"❌ Error: Stats directory not found at {STATS_COLLECTION_DIR}")
        sys.exit(1)

    # Find all Python files in immediate subdirectories of Stats_data_collection
    search_pattern = os.path.join(STATS_COLLECTION_DIR, "*", "*.py")
    scraper_scripts = glob.glob(search_pattern)
    
    # Filter out anything that shouldn't be run just in case, though pattern '*/*.py' avoids root files like Stats.py
    scraper_scripts = [s for s in scraper_scripts if os.path.isfile(s) and not s.endswith('__init__.py')]
    
    if not scraper_scripts:
        print("⚠️ No scraper scripts found. Check your directories.")
        sys.exit(1)

    print(f"Found {len(scraper_scripts)} scrapers to execute.\n")

    success_count = 0
    fail_count = 0
    failed_scripts = []

    for i, script_path in enumerate(scraper_scripts, 1):
        script_name = os.path.relpath(script_path, STATS_COLLECTION_DIR)
        print(f"[{i}/{len(scraper_scripts)}] Running {script_name}...")
        
        # It's important to run the scraper with its own directory as cwd 
        # so relative file writes (like 'data.json')) or 'data.csv')) go to the right place.
        script_dir = os.path.dirname(script_path)
        
        try:
            start_time = time.time()
            # Run the python script
            result = subprocess.run(
                [sys.executable, script_path],
                cwd=script_dir,
                capture_output=True,
                text=True,
                check=True
            )
            elapsed = time.time() - start_time
            print(f"  ✅ Success in {elapsed:.1f}s")
            success_count += 1
            
        except subprocess.CalledProcessError as e:
            elapsed = time.time() - start_time
            print(f"  ❌ FAILED in {elapsed:.1f}s")
            print(f"  Error Output:\n{e.stderr.strip()}")
            fail_count += 1
            failed_scripts.append(script_name)
        except fileNotFoundError:
            print(f"  ❌ Python executable not found: {sys.executable}")
            sys.exit(1)

    print(f"\n{'═'*70}")
    print(f"  Scraping Completed: {success_count} succeeded, {fail_count} failed")
    if failed_scripts:
        print("  Failed scripts:")
        for fs in failed_scripts:
            print(f"   - {fs}")
    print(f"{'═'*70}\n")

    # 1. Run Stats.py to evaluate all the newly pulled data
    if os.path.exists(STATS_PY):
        print(f"Executing Risk Analysis Engine: {os.path.basename(STATS_PY)}...")
        try:
            subprocess.run(
                [sys.executable, STATS_PY],
                cwd=STATS_COLLECTION_DIR,
                check=True
            )
            print("\nRisk Analysis successfully completed.")
        except subprocess.CalledProcessError:
            print("\nRisk Analysis Engine failed to run.")
    else:
        print(f"Warning: Cannot find {STATS_PY}")

    # 2. Run Weather_LLM_Strategy.py for predictive insights
    if os.path.exists(WEATHER_STRAT_PY):
        print(f"\nExecuting Weather Strategy Engine: {os.path.basename(WEATHER_STRAT_PY)}...")
        try:
            subprocess.run(
                [sys.executable, WEATHER_STRAT_PY],
                cwd=STATS_COLLECTION_DIR,
                check=True
            )
            print("\nWeather Strategy Analysis successfully completed.")
        except subprocess.CalledProcessError:
            print("\nWeather Strategy Engine failed to run.")
    else:
        print(f"Warning: Cannot find {WEATHER_STRAT_PY}")

if __name__ == "__main__":
    main()
