#!/usr/bin/env python3
"""
CLI wrapper: called by Node.js to save a user profile.

Flow:
  1.  DB save   — always fast, completes synchronously
  2.  Print {"ok": true} to stdout and flush  ← Node.js reads this, spawnSync returns
  3.  LLM thread is daemon=True, so the process exits immediately after step 2
      (daemon threads are killed on exit — that is intentional here; LLM is optional)

This guarantees the frontend never hangs on "Processing AI..." regardless of
whether the local LLM server at port 8003 is up or not.
"""
import sys
import json
import base64
import os
import traceback
import contextlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    print("Reached save_user_cli.py'), file=sys.stderr)   # stderr only — stdout is reserved for JSON
    raw  = sys.stdin.buffer.read()
    data = json.loads(raw.decode('utf-8'))

    from personeldata import save_user_profile

    cv_b64      = data.get("cv_file_b64", "")
    cv_filename = data.get("cv_filename", "")
    cv_bytes    = base64.b64decode(cv_b64) if cv_b64 else b""

    # All print() from personeldata.py → stderr so stdout stays clean for Node.js
    with contextlib.redirect_stdout(sys.stderr):
        save_user_profile(
            email              = data["email"],
            name               = data["name"],
            location           = data.get("location", ""),
            github_description = data.get("github_description", ""),
            languages          = data.get("languages", []),
            cv_file_bytes      = cv_bytes,
            cv_filename        = cv_filename,
            access_token       = data.get("access_token", ""),
            refresh_token      = data.get("refresh_token", ""),
        )

    # ── Send success immediately to Node.js ────────────────────────────────────
    # Node.js will parse this JSON and instantly resolve the POST request,
    # leaving this Python process running in the background to finish the LLM task.
    sys.stdout.write(json.dumps({"ok": True}) + "\n")
    sys.stdout.flush()
    
    # DO NOT call sys.exit(0) here!
    # If we exit, the background thread in personeldata.py gets killed.
    # Python will naturally exit once all non-daemon threads (the LLM process) finish.

except Exception as e:
    sys.stdout.write(json.dumps({"ok": False, "error": traceback.format_exc()}) + "\n")
    sys.stdout.flush()
    sys.exit(1)
