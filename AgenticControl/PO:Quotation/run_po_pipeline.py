import sys
import json
import os
import traceback

# Add local directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from po_processor import process_po
from quotation_predictor import predict_quotation, _open_db

def get_predictions_json(db_path, tables_data):
    # Fetch predicted rows from the prediction DB
    if not os.path.exists(db_path):
        return []
        
    conn = _open_db(db_path)
    all_rows = []
    
    for tbl_data in tables_data:
        pt = tbl_data.get("prediction_table")
        if not pt: continue
        try:
            cur = conn.execute(f'SELECT * FROM "{pt}"')
            rows = [dict(r) for r in cur.fetchall()]
            all_rows.extend(rows)
        except Exception as e:
            pass
            
    conn.close()
    return all_rows

def main():
    try:
        raw = sys.stdin.read().strip()
        if not raw:
            print(json.dumps({"error": "No input provided"}))
            return
            
        payload = json.loads(raw)
        file_path = payload.get("file_path")
        
        if not file_path or not os.path.exists(file_path):
            print(json.dumps({"error": f"File not found: {file_path}"}))
            return
            
        # 1. Process PO
        po_result = process_po(file_path)
        if not po_result.get("tables_saved"):
            print(json.dumps({"error": "Failed to process PO or no tables extracted"}))
            return
            
        # 2. Predict Quotations
        source_name = os.path.basename(file_path)
        quote_result = predict_quotation(source_file=source_name)
        
        if not quote_result or "tables" not in quote_result:
            print(json.dumps({"error": "Failed to predict quotations"}))
            return
            
        # 3. Retrieve final JSON for frontend
        pred_db = quote_result.get("predictions_db")
        final_rows = get_predictions_json(pred_db, quote_result["tables"])
        
        print(json.dumps({
            "success": True,
            "predictions": final_rows,
            "po_tables": po_result.get("tables_saved")
        }))
        
    except Exception as e:
        print(json.dumps({"error": str(e), "traceback": traceback.format_exc()}))

if __name__ == "__main__":
    main()
