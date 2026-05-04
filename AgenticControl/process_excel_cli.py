#!/usr/bin/env python3
import sys
import json
import os
import traceback
import contextlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    if len(sys.argv) < 2:
        raise ValueError("Missing excel file path")
        
    file_path = sys.argv[1]
    
    from Excel_Processor import init_db, process_excel
    
    init_db()
    
    # Redirect stdout to stderr so our JSON response isn't corrupted
    with contextlib.redirect_stdout(sys.stderr):
        print(f"Starting Excel processing for: {file_path}", flush=True)
        process_excel(file_path)
    
    sys.stdout.write(json.dumps({"ok": True}) + "\n")
    sys.stdout.flush()
    
    # Clean up the temp file
    try:
        os.remove(file_path)
    except Exception as cleanup_err:
        print(f"Failed to clean up temp file: {cleanup_err}", file=sys.stderr)
        
    sys.exit(0)
    
except Exception as e:
    sys.stdout.write(json.dumps({"ok": False, "error": traceback.format_exc()}) + "\n")
    sys.stdout.flush()
    sys.exit(1)
