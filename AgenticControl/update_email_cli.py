import sys
import json
from user_review_email import update_single_email

if __name__ == "__main__":
    try:
        input_data = sys.stdin.read()
        payload = json.loads(input_data)
        
        target_id = payload.get("id")
        feedback = payload.get("feedback")
        
        if not target_id or not feedback:
            print(json.dumps({"ok": False, "error": "Missing id or feedback"}))
            sys.exit(1)
            
        success = update_single_email(db_id=target_id, feedback=feedback)
        
        if success:
            print(json.dumps({"ok": True}))
        else:
            print(json.dumps({"ok": False, "error": "Unknown error during email update"}))
            
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        sys.exit(1)
