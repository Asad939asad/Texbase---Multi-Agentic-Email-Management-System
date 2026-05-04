#!/usr/bin/env python3
"""
CLI wrapper: called by Node.js to check if user exists.
Usage: python3 check_user_cli.py <email>
Output: JSON → {"exists": true} or {"exists": false}
"""
import sys
import json
import os

# Ensure we can import personeldata from the same folder
sys.path.insert(0, os.path.dirname(__file__))
from personeldata import check_user_exists

if len(sys.argv) < 2:
    print(json.dumps({"error": "No email provided"}))
    sys.exit(1)

email = sys.argv[1]
exists = check_user_exists(email)
print(json.dumps({"exists": exists}))
