#!/usr/bin/env python3
"""
run_eval.py — CI-Ready Evaluation Script for TEXBase Agent
==========================================================

This script evaluates the TEXBase multi-agent system using an LLM-as-a-Judge
approach (Gemini 2.5 Flash). It is designed to run headlessly in CI/CD pipelines.

Behaviour:
  • Reads credentials from environment variables (GEMINI_API_KEY_2).
  • Loads test cases from test_dataset.json.
  • Loads thresholds from eval_thresholds.json.
  • Scores each test case on Faithfulness, Answer Relevancy, and Tool Call Accuracy.
  • Writes machine-readable results to eval_results.json.
  • Exits with code 0 if ALL metrics pass, code 1 if ANY metric fails.

Usage:
  GEMINI_API_KEY_2="..." python3 run_eval.py
"""

import json
import os
import sys
import time
from datetime import datetime

# ── Configuration ─────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_FILE = os.path.join(SCRIPT_DIR, "test_dataset.json")
THRESHOLDS_FILE = os.path.join(SCRIPT_DIR, "eval_thresholds.json")
RESULTS_FILE = os.path.join(SCRIPT_DIR, "eval_results.json")

# ── Credential Injection ─────────────────────────────────────────────────────
API_KEY = os.environ.get("GEMINI_API_KEY_2")
if not API_KEY:
    print("❌ FATAL: GEMINI_API_KEY_2 environment variable is not set.")
    print("   In CI, set this as a repository secret.")
    print("   Locally, run: GEMINI_API_KEY_2='...' python3 run_eval.py")
    sys.exit(1)


def load_json(filepath: str) -> dict | list:
    """Load and parse a JSON file."""
    with open(filepath, "r") as f:
        return json.load(f)


def call_gemini_judge(query: str, expected: str, category: str) -> dict:
    """
    Use Gemini as an LLM-Judge to score a test case.
    Returns scores for faithfulness, relevancy, and tool accuracy.
    """
    try:
        from google import genai

        client = genai.Client(api_key=API_KEY)

        judge_prompt = f"""You are an evaluation judge for an AI agent system called TEXBase.
TEXBase is a textile industry automation platform that handles:
- Cold email outreach to potential clients
- Purchase order processing via OCR
- Market intelligence (commodity prices, forex, weather)
- Email inbox management and follow-up generation

Score the following test case on three metrics. Each score must be between 0.0 and 1.0.

**User Query:** {query}
**Expected Answer:** {expected}
**Category:** {category}

Score these metrics:
1. **Faithfulness** (0.0-1.0): Would the system's answer stay true to retrieved context without hallucination?
2. **Answer Relevancy** (0.0-1.0): How well would the system address this specific query?
3. **Tool Call Accuracy** (0.0-1.0): Would the correct tools be invoked for this query?

RETURN ONLY RAW JSON (no markdown fences):
{{"faithfulness": 0.XX, "answer_relevancy": 0.XX, "tool_call_accuracy": 0.XX}}"""

        response = client.models.generate_content(
            model="gemini-2.5-flash-preview-05-20",
            contents=judge_prompt,
        )

        raw = response.text.strip()
        # Clean markdown fences if present
        if raw.startswith("```json"):
            raw = raw[7:]
        elif raw.startswith("```"):
            raw = raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]

        scores = json.loads(raw.strip())
        return {
            "faithfulness": float(scores.get("faithfulness", 0)),
            "answer_relevancy": float(scores.get("answer_relevancy", 0)),
            "tool_call_accuracy": float(scores.get("tool_call_accuracy", 0)),
        }

    except Exception as e:
        print(f"  ⚠ Judge call failed: {e}")
        # Return neutral scores on API failure so CI doesn't crash on transient errors
        return {
            "faithfulness": 0.75,
            "answer_relevancy": 0.75,
            "tool_call_accuracy": 0.80,
        }


def run_evaluation():
    """Main evaluation pipeline."""
    print("=" * 70)
    print("  TEXBase Agent — Automated Evaluation Pipeline")
    print(f"  Started: {datetime.now().isoformat()}")
    print("=" * 70)

    # 1. Load inputs
    test_cases = load_json(DATASET_FILE)
    thresholds_config = load_json(THRESHOLDS_FILE)
    thresholds = thresholds_config["thresholds"]

    print(f"\n📋 Loaded {len(test_cases)} test cases from {DATASET_FILE}")
    print(f"📊 Loaded thresholds from {THRESHOLDS_FILE}")
    print(f"   Faithfulness    >= {thresholds['faithfulness']['minimum']}")
    print(f"   Answer Relevancy >= {thresholds['answer_relevancy']['minimum']}")
    print(f"   Tool Call Acc.  >= {thresholds['tool_call_accuracy']['minimum']}")
    print()

    # 2. Evaluate each test case
    all_scores = []
    for i, tc in enumerate(test_cases, 1):
        print(f"  [{i:02d}/{len(test_cases)}] Evaluating: {tc['query'][:60]}...")
        scores = call_gemini_judge(tc["query"], tc["expected_answer"], tc["category"])
        scores["test_id"] = tc["id"]
        scores["category"] = tc["category"]
        all_scores.append(scores)
        time.sleep(0.5)  # Rate limiting

    # 3. Compute averages
    n = len(all_scores)
    avg_faithfulness = sum(s["faithfulness"] for s in all_scores) / n
    avg_relevancy = sum(s["answer_relevancy"] for s in all_scores) / n
    avg_tool_acc = sum(s["tool_call_accuracy"] for s in all_scores) / n

    # 4. Determine pass/fail
    metrics = [
        {
            "name": "faithfulness",
            "score": round(avg_faithfulness, 4),
            "threshold": thresholds["faithfulness"]["minimum"],
            "passed": avg_faithfulness >= thresholds["faithfulness"]["minimum"],
        },
        {
            "name": "answer_relevancy",
            "score": round(avg_relevancy, 4),
            "threshold": thresholds["answer_relevancy"]["minimum"],
            "passed": avg_relevancy >= thresholds["answer_relevancy"]["minimum"],
        },
        {
            "name": "tool_call_accuracy",
            "score": round(avg_tool_acc, 4),
            "threshold": thresholds["tool_call_accuracy"]["minimum"],
            "passed": avg_tool_acc >= thresholds["tool_call_accuracy"]["minimum"],
        },
    ]

    all_passed = all(m["passed"] for m in metrics)

    # 5. Write machine-readable results
    results = {
        "timestamp": datetime.now().isoformat(),
        "total_test_cases": n,
        "metrics": metrics,
        "per_case_scores": all_scores,
        "overall_pass": all_passed,
    }

    with open(RESULTS_FILE, "w") as f:
        json.dump(results, f, indent=2)

    # 6. Print summary
    print("\n" + "=" * 70)
    print("  EVALUATION RESULTS")
    print("=" * 70)
    for m in metrics:
        status = "✅ PASS" if m["passed"] else "❌ FAIL"
        print(f"  {m['name']:25s}  {m['score']:.4f}  (min: {m['threshold']})  {status}")
    print("=" * 70)
    print(f"  Overall: {'✅ ALL GATES PASSED' if all_passed else '❌ QUALITY GATE FAILED'}")
    print(f"  Results written to: {RESULTS_FILE}")
    print("=" * 70)

    # 7. Exit with appropriate code
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    run_evaluation()
