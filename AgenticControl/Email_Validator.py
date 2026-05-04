import requests
import pandas as pd
import os

from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.environ.get('WORKSPACE_ROOT', os.path.join(os.environ.get('WORKSPACE_ROOT', '.'), 'backend/.env'))))
hunter_api_key = os.getenv("HUNTER_API_KEY")


def verify_email_with_hunter(email: str) -> dict:
    try:
        resp = requests.get(
            "https://api.hunter.io/v2/email-verifier",
            params={"email": email, "api_key": hunter_api_key},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})
        print(f"  Hunter [{data.get('status')} {data.get('score')}%] {email}")
        if data.get("status") == "valid":
            return True
        else:
            return False
    except Exception as err:
        print(f"  Hunter error for {email}: {err}")
        return False

# email = "asadirfan358@gmail.com"
# verify_email_with_hunter(email)