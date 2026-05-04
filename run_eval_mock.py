#!/usr/bin/env python3
"""
run_eval_mock.py — Offline Mock Evaluation for TEXBase Agent
=============================================================

Simulates the evaluation pipeline with pre-defined realistic scores.
Use this to:
  1. Demonstrate a PASSING quality gate  (default)
  2. Demonstrate a FAILING quality gate  (--degrade flag)

Usage:
  python3 run_eval_mock.py             # Normal run  → exit 0
  python3 run_eval_mock.py --degrade   # Broken agent → exit 1
"""

import json
import sys
import os
from datetime import datetime

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
THRESHOLDS_FILE = os.path.join(SCRIPT_DIR, "eval_thresholds.json")
RESULTS_FILE    = os.path.join(SCRIPT_DIR, "eval_results.json")
DATASET_FILE    = os.path.join(SCRIPT_DIR, "test_dataset.json")

DEGRADE = "--degrade" in sys.argv

# ── Simulated per-case scores ────────────────────────────────────────────────
# Normal state: agent is healthy, all scores above thresholds
NORMAL_SCORES = [
    {"faithfulness": 0.91, "answer_relevancy": 0.88, "tool_call_accuracy": 0.95},
    {"faithfulness": 0.85, "answer_relevancy": 0.92, "tool_call_accuracy": 0.87},
    {"faithfulness": 0.78, "answer_relevancy": 0.81, "tool_call_accuracy": 0.93},
    {"faithfulness": 0.88, "answer_relevancy": 0.76, "tool_call_accuracy": 0.82},
    {"faithfulness": 0.93, "answer_relevancy": 0.89, "tool_call_accuracy": 0.96},
    {"faithfulness": 0.72, "answer_relevancy": 0.84, "tool_call_accuracy": 0.88},
    {"faithfulness": 0.86, "answer_relevancy": 0.91, "tool_call_accuracy": 0.91},
    {"faithfulness": 0.90, "answer_relevancy": 0.78, "tool_call_accuracy": 0.84},
    {"faithfulness": 0.83, "answer_relevancy": 0.87, "tool_call_accuracy": 0.89},
    {"faithfulness": 0.79, "answer_relevancy": 0.82, "tool_call_accuracy": 0.92},
    {"faithfulness": 0.95, "answer_relevancy": 0.93, "tool_call_accuracy": 0.97},
    {"faithfulness": 0.74, "answer_relevancy": 0.77, "tool_call_accuracy": 0.81},
    {"faithfulness": 0.87, "answer_relevancy": 0.85, "tool_call_accuracy": 0.90},
    {"faithfulness": 0.92, "answer_relevancy": 0.90, "tool_call_accuracy": 0.94},
    {"faithfulness": 0.81, "answer_relevancy": 0.83, "tool_call_accuracy": 0.86},
    {"faithfulness": 0.76, "answer_relevancy": 0.79, "tool_call_accuracy": 0.83},
    {"faithfulness": 0.89, "answer_relevancy": 0.86, "tool_call_accuracy": 0.91},
    {"faithfulness": 0.94, "answer_relevancy": 0.88, "tool_call_accuracy": 0.96},
    {"faithfulness": 0.82, "answer_relevancy": 0.80, "tool_call_accuracy": 0.85},
    {"faithfulness": 0.77, "answer_relevancy": 0.84, "tool_call_accuracy": 0.88},
    {"faithfulness": 0.91, "answer_relevancy": 0.92, "tool_call_accuracy": 0.93},
    {"faithfulness": 0.84, "answer_relevancy": 0.87, "tool_call_accuracy": 0.89},
]

# Degraded state: system prompt corrupted, RAG context removed
# Faithfulness collapses (hallucinations), tool accuracy drops
DEGRADED_SCORES = [
    {"faithfulness": 0.41, "answer_relevancy": 0.55, "tool_call_accuracy": 0.60},
    {"faithfulness": 0.38, "answer_relevancy": 0.62, "tool_call_accuracy": 0.52},
    {"faithfulness": 0.52, "answer_relevancy": 0.48, "tool_call_accuracy": 0.65},
    {"faithfulness": 0.35, "answer_relevancy": 0.58, "tool_call_accuracy": 0.57},
    {"faithfulness": 0.44, "answer_relevancy": 0.51, "tool_call_accuracy": 0.63},
    {"faithfulness": 0.49, "answer_relevancy": 0.45, "tool_call_accuracy": 0.55},
    {"faithfulness": 0.37, "answer_relevancy": 0.60, "tool_call_accuracy": 0.48},
    {"faithfulness": 0.53, "answer_relevancy": 0.53, "tool_call_accuracy": 0.61},
    {"faithfulness": 0.40, "answer_relevancy": 0.47, "tool_call_accuracy": 0.54},
    {"faithfulness": 0.46, "answer_relevancy": 0.59, "tool_call_accuracy": 0.67},
    {"faithfulness": 0.33, "answer_relevancy": 0.44, "tool_call_accuracy": 0.49},
    {"faithfulness": 0.55, "answer_relevancy": 0.63, "tool_call_accuracy": 0.72},
    {"faithfulness": 0.39, "answer_relevancy": 0.50, "tool_call_accuracy": 0.58},
    {"faithfulness": 0.42, "answer_relevancy": 0.56, "tool_call_accuracy": 0.53},
    {"faithfulness": 0.48, "answer_relevancy": 0.42, "tool_call_accuracy": 0.62},
    {"faithfulness": 0.36, "answer_relevancy": 0.61, "tool_call_accuracy": 0.50},
    {"faithfulness": 0.43, "answer_relevancy": 0.49, "tool_call_accuracy": 0.64},
    {"faithfulness": 0.51, "answer_relevancy": 0.54, "tool_call_accuracy": 0.59},
    {"faithfulness": 0.34, "answer_relevancy": 0.46, "tool_call_accuracy": 0.56},
    {"faithfulness": 0.47, "answer_relevancy": 0.57, "tool_call_accuracy": 0.68},
    {"faithfulness": 0.45, "answer_relevancy": 0.52, "tool_call_accuracy": 0.66},
    {"faithfulness": 0.50, "answer_relevancy": 0.60, "tool_call_accuracy": 0.70},
]

def main():
    scores_data = DEGRADED_SCORES if DEGRADE else NORMAL_SCORES

    # Load config files
    with open(THRESHOLDS_FILE) as f:
        thresholds_config = json.load(f)
    thresholds = thresholds_config["thresholds"]

    with open(DATASET_FILE) as f:
        test_cases = json.load(f)

    mode = "DEGRADED AGENT (--degrade)" if DEGRADE else "NORMAL AGENT"

    print("=" * 70)
    print("  TEXBase Agent — Quality Gate Evaluation (Mock)")
    print(f"  Mode: {mode}")
    print(f"  Started: {datetime.now().isoformat()}")
    print("=" * 70)
    print(f"\n📋 Evaluating {len(test_cases)} test cases...")
    print()

    # Attach test metadata
    all_scores = []
    for i, (tc, s) in enumerate(zip(test_cases, scores_data), 1):
        label = "DEGRADED" if DEGRADE else "ok"
        print(f"  [{i:02d}/{len(test_cases)}] {tc['query'][:55]:<55} [{label}]")
        all_scores.append({
            "test_id": tc["id"],
            "category": tc["category"],
            **s
        })

    # Compute averages
    n = len(all_scores)
    avg_faith   = sum(s["faithfulness"]       for s in all_scores) / n
    avg_relev   = sum(s["answer_relevancy"]   for s in all_scores) / n
    avg_tool    = sum(s["tool_call_accuracy"] for s in all_scores) / n

    # Pass/fail
    metrics = [
        {
            "name": "faithfulness",
            "score": round(avg_faith, 4),
            "threshold": thresholds["faithfulness"]["minimum"],
            "passed": avg_faith >= thresholds["faithfulness"]["minimum"],
        },
        {
            "name": "answer_relevancy",
            "score": round(avg_relev, 4),
            "threshold": thresholds["answer_relevancy"]["minimum"],
            "passed": avg_relev >= thresholds["answer_relevancy"]["minimum"],
        },
        {
            "name": "tool_call_accuracy",
            "score": round(avg_tool, 4),
            "threshold": thresholds["tool_call_accuracy"]["minimum"],
            "passed": avg_tool >= thresholds["tool_call_accuracy"]["minimum"],
        },
    ]

    all_passed = all(m["passed"] for m in metrics)

    # Write results
    results = {
        "timestamp": datetime.now().isoformat(),
        "mode": "degraded" if DEGRADE else "normal",
        "total_test_cases": n,
        "metrics": metrics,
        "per_case_scores": all_scores,
        "overall_pass": all_passed,
    }
    with open(RESULTS_FILE, "w") as f:
        json.dump(results, f, indent=2)

    # Print summary
    print("\n" + "=" * 70)
    print("  EVALUATION RESULTS")
    print("=" * 70)
    for m in metrics:
        status = "✅ PASS" if m["passed"] else "❌ FAIL"
        print(f"  {m['name']:25s}  {m['score']:.4f}  (min: {m['threshold']})  {status}")
    print("=" * 70)
    print(f"  Overall: {'✅ ALL GATES PASSED — ready for deployment' if all_passed else '❌ QUALITY GATE FAILED — deployment blocked'}")
    print(f"  Results written to: {RESULTS_FILE}")
    print("=" * 70)

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
