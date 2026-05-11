from flask import Flask, request, jsonify
from flask_cors import CORS
import feedback_logger

app = Flask(__name__)
# Explicit CORS configuration for the frontend origin
CORS(app, resources={r"/api/*": {"origins": "http://localhost:5173"}})

@app.errorhandler(Exception)
def handle_exception(e):
    # Pass through HTTP errors
    if hasattr(e, 'code'):
        return jsonify({"error": str(e)}), e.code
    # Handle non-HTTP exceptions only
    print(f"Server Error: {e}")
    return jsonify({"error": "Internal Server Error", "details": str(e)}), 500

@app.route('/api/feedback/market_analysis', methods=['POST'])
def feedback_market():
    data = request.json
    feedback_logger.log_feedback(
        section='market_analysis',
        feedback=data.get('feedback'),
        user_input=data.get('user_input'),
        agent_response=data.get('agent_response'),
        parameter_name=data.get('parameter_name'),
        prediction_summary=data.get('prediction_summary'),
        flagged_excerpt=data.get('flagged_excerpt'),
        user_comment=data.get('user_comment')
    )
    return jsonify({"status": "ok"})

@app.route('/api/feedback/market_chat', methods=['POST'])
def feedback_market_chat():
    data = request.json
    feedback_logger.log_feedback(
        section='market_chat',
        feedback=data.get('feedback'),
        user_input=data.get('user_input'),
        agent_response=data.get('agent_response'),
        user_comment=data.get('user_comment')
    )
    return jsonify({"status": "ok"})

@app.route('/api/feedback/email_editor', methods=['POST'])
def feedback_email():
    data = request.json
    feedback_logger.log_feedback(
        section='email_editor',
        feedback=data.get('feedback'),
        user_input=data.get('user_input'),
        agent_response=data.get('agent_response'),
        tone_requested=data.get('tone_requested'),
        draft_length_chars=data.get('draft_length_chars')
    )
    return jsonify({"status": "ok"})

@app.route('/api/feedback/inbox_flow', methods=['POST'])
def feedback_inbox():
    data = request.json
    feedback_logger.log_feedback(
        section='inbox_flow',
        feedback=data.get('feedback'),
        user_input=data.get('user_input'),
        agent_response=data.get('agent_response'),
        pipeline_stage=data.get('pipeline_stage'),
        recipient_hint=data.get('recipient_hint')
    )
    return jsonify({"status": "ok"})

@app.route('/api/feedback/po_quotation', methods=['POST'])
def feedback_po():
    data = request.json
    predicted = data.get('predicted_price')
    actual = data.get('actual_price')
    price_delta = None
    
    try:
        if predicted is not None and actual is not None:
            price_delta = abs(float(predicted) - float(actual))
    except (ValueError, TypeError):
        pass

    feedback_logger.log_feedback(
        section='po_quotation',
        feedback=data.get('feedback'),
        user_input=data.get('user_input'),
        agent_response=data.get('agent_response'),
        predicted_price=predicted,
        actual_price=actual,
        price_delta=price_delta,
        item_description=data.get('item_description'),
        correction_note=data.get('correction_note')
    )
    return jsonify({"status": "ok"})

@app.route('/api/feedback/stats', methods=['GET'])
def get_stats():
    logs = feedback_logger.get_all_logs()
    total = len(logs)
    if total == 0:
        return jsonify({"total": 0, "by_section": {}, "negative_rate": 0, "partial_rate": 0})
    
    sections = {}
    bad_count = 0
    partial_count = 0
    
    for l in logs:
        s = l['section']
        sections[s] = sections.get(s, 0) + 1
        if l['feedback'] == 'bad': bad_count += 1
        if l['feedback'] == 'partial': partial_count += 1
        
    return jsonify({
        "total": total,
        "by_section": sections,
        "negative_rate": (bad_count / total) * 100,
        "partial_rate": (partial_count / total) * 100
    })

if __name__ == "__main__":
    feedback_logger.init_db()
    app.run(port=5050, debug=True)
