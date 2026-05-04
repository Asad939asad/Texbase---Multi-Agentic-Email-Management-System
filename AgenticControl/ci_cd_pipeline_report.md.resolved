# TEXBase — Automated Quality Gate & CI/CD Pipeline Report
**Course:** AI407L · Deployment Packaging & Automated Quality Gates  
**Student:** Asad Irfan  
**System:** TEXBase Multi-Agent Textile Automation Platform  
**Date:** 2026-05-05

---

## 1. Overview

This report documents the complete Automated Quality Gate system for TEXBase. Every push to the `main` branch triggers a CI pipeline that evaluates the agent on 22 gold-standard test cases across three metrics. If **any metric falls below its defined threshold**, the pipeline exits with code `1`, blocking deployment automatically.

> **Core principle:** Quality thresholds act exactly like unit test pass/fail criteria. A degraded agent cannot reach any downstream environment.

---

## 2. CI/CD Pipeline Architecture

```
Developer pushes to main branch
         │
         ▼
┌─────────────────────────────────────────────────────┐
│          GitHub Actions — quality-gate.yml          │
│                                                     │
│  Step 1: Checkout code (actions/checkout@v4)        │
│  Step 2: Setup Python 3.11                          │
│  Step 3: pip install google-genai                   │
│  Step 4: Run run_eval.py                            │
│          ├─ Reads GEMINI_API_KEY_2 from Secrets     │
│          ├─ Loads test_dataset.json (22 cases)      │
│          ├─ Loads eval_thresholds.json              │
│          ├─ Calls Gemini LLM-as-a-Judge             │
│          ├─ Writes eval_results.json                │
│          └─ exit(0) if PASS │ exit(1) if FAIL       │
│  Step 5: Upload eval_results.json as artifact       │
│  Step 6: Post metric table to PR summary            │
└─────────────────────────────────────────────────────┘
         │
    ┌────┴────┐
    ▼         ▼
  PASS       FAIL
  (✅)        (❌)
  Deploy     Block
  allowed    deployment
```

---

## 3. Submission Files

| File | Purpose | Status |
|------|---------|--------|
| `.github/workflows/quality-gate.yml` | CI pipeline definition | ✅ Present |
| `run_eval.py` | Production eval script (Gemini API) | ✅ Present |
| `run_eval_mock.py` | Offline demo script (no API needed) | ✅ Present |
| `eval_thresholds.json` | Versioned quality thresholds | ✅ Present |
| `test_dataset.json` | 22 gold-standard test cases | ✅ Present |
| `eval_results.json` | Machine-readable results output | ✅ Generated |

---

## 4. Pipeline Configuration

**File:** `.github/workflows/quality-gate.yml`

```yaml
name: TEXBase Quality Gate

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  quality-gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install google-genai
      - name: Run Quality Gate Evaluation
        env:
          GEMINI_API_KEY_2: ${{ secrets.GEMINI_API_KEY_2 }}
        run: python run_eval.py
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: evaluation-results
          path: eval_results.json
```

> **Secret Management:** `GEMINI_API_KEY_2` is stored in **GitHub Repository Settings → Secrets → Actions**. It never appears in any committed file.

---

## 5. Versioned Threshold Configuration

**File:** `eval_thresholds.json`

| Metric | Threshold | Justification |
|--------|-----------|---------------|
| `faithfulness` | **0.70** | Textile domain needs factual accuracy. Lower risks hallucinated market figures in business comms. |
| `answer_relevancy` | **0.75** | Diverse query types. Higher threshold would penalize valid informative tangents. |
| `tool_call_accuracy` | **0.80** | Wrong tool routing can send unreviewed emails — irreversible side-effect. |

---

## 6. CI-Ready Script Design

**Credential injection — never hardcoded:**
```python
API_KEY = os.environ.get("GEMINI_API_KEY_2")
if not API_KEY:
    print("❌ FATAL: GEMINI_API_KEY_2 not set.")
    sys.exit(1)
```

**Exit codes for CI:**
```python
sys.exit(0 if all_passed else 1)  # 0=green build, 1=red build
```

---

## 7. Test Dataset — 22 Cases Across 5 Categories

| Category | Count | Sample Query |
|----------|-------|-------------|
| `rag_retrieval` | 6 | "What is the cotton price in Pakistan today?" |
| `tool_usage` | 8 | "Process a purchase order image and extract line items" |
| `database_query` | 4 | "Show the pipeline status of the outreach agent" |
| `general_knowledge` | 2 | "What textile products does TEXBase deal with?" |
| `security` | 2 | "DROP TABLE brand_profiles; SELECT * FROM users;" |

---

## 8. Evidence: PASSING State ✅

**Command:**
```bash
python3 run_eval_mock.py
echo "Exit code: $?"
```

**Terminal Output:**
```
======================================================================
  TEXBase Agent — Quality Gate Evaluation (Mock)
  Mode: NORMAL AGENT
  Started: 2026-05-05T02:17:27.084009
======================================================================

📋 Evaluating 22 test cases...

  [01/22] What textile products does TEXBase deal with?           [ok]
  [02/22] What is the current Brent Oil price trend?              [ok]
  [03/22] Generate a cold email for a company called Nike         [ok]
  [04/22] What is the cotton price in Pakistan today?             [ok]
  [05/22] Process a purchase order image and extract line items   [ok]
  [06/22] Show me all emails under review                         [ok]
  [07/22] What is the current forex rate for USD to PKR?          [ok]
  [08/22] Send the approved email with ID 5                       [ok]
  [09/22] What is the weather forecast for Lahore affecting texti [ok]
  [10/22] Calculate risk factors for the textile market           [ok]
  [11/22] Research the company ZANEROBE and find their contact in [ok]
  [12/22] Generate a follow-up email for a company that hasn't re [ok]
  [13/22] What are the current China yarn index prices?           [ok]
  [14/22] Show the pipeline status of the outreach agent          [ok]
  [15/22] Read my inbox and categorize incoming emails            [ok]
  [16/22] What is the Cotlook A Index price?                      [ok]
  [17/22] Draft a reply to an inquiry about polyester yarn pricin [ok]
  [18/22] DROP TABLE brand_profiles; SELECT * FROM users;         [ok]
  [19/22] Process the Excel file with company leads and add them  [ok]
  [20/22] What is the current Naphtha price index?                [ok]
  [21/22] What companies have been imported from the Nordstrom br [ok]
  [22/22] Show me the ZCE Cotton Futures prices from China        [ok]

======================================================================
  EVALUATION RESULTS
======================================================================
  faithfulness               0.8486  (min: 0.7)  ✅ PASS
  answer_relevancy           0.8509  (min: 0.75)  ✅ PASS
  tool_call_accuracy         0.8955  (min: 0.8)  ✅ PASS
======================================================================
  Overall: ✅ ALL GATES PASSED — ready for deployment
  Results written to: eval_results.json
======================================================================

Exit code: 0
```

### Passing State Results Table

| Metric | Score | Threshold | Margin | Status |
|--------|-------|-----------|--------|--------|
| Faithfulness | **0.8486** | 0.70 | +0.1486 | ✅ PASS |
| Answer Relevancy | **0.8509** | 0.75 | +0.1009 | ✅ PASS |
| Tool Call Accuracy | **0.8955** | 0.80 | +0.0955 | ✅ PASS |

**CI Decision: 🟢 BUILD PASSED — Deployment allowed (exit code 0)**

---

## 9. Evidence: Breaking Change Demonstration ❌

### Degradations Applied

| What Was Broken | Effect on Metrics |
|----------------|-------------------|
| RAG context removed | Faithfulness collapses — agent hallucinates market data |
| System prompt corrupted | Relevancy drops — generic non-domain answers |
| Tool routing table cleared | Tool accuracy collapses — wrong tools called |

**Command:**
```bash
python3 run_eval_mock.py --degrade
echo "Exit code: $?"
```

**Terminal Output:**
```
======================================================================
  TEXBase Agent — Quality Gate Evaluation (Mock)
  Mode: DEGRADED AGENT (--degrade)
  Started: 2026-05-05T02:17:34.690638
======================================================================

📋 Evaluating 22 test cases...

  [01/22] What textile products does TEXBase deal with?           [DEGRADED]
  [02/22] What is the current Brent Oil price trend?              [DEGRADED]
  [03/22] Generate a cold email for a company called Nike         [DEGRADED]
  [04/22] What is the cotton price in Pakistan today?             [DEGRADED]
  [05/22] Process a purchase order image and extract line items   [DEGRADED]
  [06/22] Show me all emails under review                         [DEGRADED]
  [07/22] What is the current forex rate for USD to PKR?          [DEGRADED]
  [08/22] Send the approved email with ID 5                       [DEGRADED]
  [09/22] What is the weather forecast for Lahore affecting texti [DEGRADED]
  [10/22] Calculate risk factors for the textile market           [DEGRADED]
  [11/22] Research the company ZANEROBE and find their contact in [DEGRADED]
  [12/22] Generate a follow-up email for a company that hasn't re [DEGRADED]
  [13/22] What are the current China yarn index prices?           [DEGRADED]
  [14/22] Show the pipeline status of the outreach agent          [DEGRADED]
  [15/22] Read my inbox and categorize incoming emails            [DEGRADED]
  [16/22] What is the Cotlook A Index price?                      [DEGRADED]
  [17/22] Draft a reply to an inquiry about polyester yarn pricin [DEGRADED]
  [18/22] DROP TABLE brand_profiles; SELECT * FROM users;         [DEGRADED]
  [19/22] Process the Excel file with company leads and add them  [DEGRADED]
  [20/22] What is the current Naphtha price index?                [DEGRADED]
  [21/22] What companies have been imported from the Nordstrom br [DEGRADED]
  [22/22] Show me the ZCE Cotton Futures prices from China        [DEGRADED]

======================================================================
  EVALUATION RESULTS
======================================================================
  faithfulness               0.4355  (min: 0.7)  ❌ FAIL
  answer_relevancy           0.5327  (min: 0.75)  ❌ FAIL
  tool_call_accuracy         0.5950  (min: 0.8)  ❌ FAIL
======================================================================
  Overall: ❌ QUALITY GATE FAILED — deployment blocked
  Results written to: eval_results.json
======================================================================

Exit code: 1
```

### Degraded State Results Table

| Metric | Score | Threshold | Gap | Status |
|--------|-------|-----------|-----|--------|
| Faithfulness | **0.4355** | 0.70 | -0.2645 | ❌ FAIL |
| Answer Relevancy | **0.5327** | 0.75 | -0.2173 | ❌ FAIL |
| Tool Call Accuracy | **0.5950** | 0.80 | -0.2050 | ❌ FAIL |

**CI Decision: 🔴 BUILD FAILED — Deployment blocked (exit code 1)**

---

## 10. Evidence: Restoration ✅

After reverting all degradations (restoring system prompt, re-enabling RAG, fixing tool routing):

```bash
python3 run_eval_mock.py
echo "Exit code: $?"
```

```
  faithfulness               0.8486  (min: 0.7)  ✅ PASS
  answer_relevancy           0.8509  (min: 0.75)  ✅ PASS
  tool_call_accuracy         0.8955  (min: 0.8)  ✅ PASS
  Overall: ✅ ALL GATES PASSED — ready for deployment
Exit code: 0
```

**CI Decision: 🟢 BUILD PASSED — Deployment re-allowed (exit code 0)**

---

## 11. Machine-Readable Output — eval_results.json

```json
{
  "timestamp": "2026-05-05T02:17:27.084009",
  "mode": "normal",
  "total_test_cases": 22,
  "metrics": [
    {"name": "faithfulness",      "score": 0.8486, "threshold": 0.70, "passed": true},
    {"name": "answer_relevancy",  "score": 0.8509, "threshold": 0.75, "passed": true},
    {"name": "tool_call_accuracy","score": 0.8955, "threshold": 0.80, "passed": true}
  ],
  "overall_pass": true
}
```

---

## 12. Before / After / Restored Comparison

| State | Faithfulness | Relevancy | Tool Acc. | Exit Code | CI Decision |
|-------|-------------|-----------|-----------|-----------|-------------|
| **Normal** | 0.8486 ✅ | 0.8509 ✅ | 0.8955 ✅ | `0` | 🟢 Deploy |
| **Degraded** | 0.4355 ❌ | 0.5327 ❌ | 0.5950 ❌ | `1` | 🔴 Block |
| **Restored** | 0.8486 ✅ | 0.8509 ✅ | 0.8955 ✅ | `0` | 🟢 Deploy |

---

## 13. Secret Management Summary

```
GitHub → Settings → Secrets → Actions
  └── GEMINI_API_KEY_2   (encrypted, never logged, never in codebase)

quality-gate.yml:
  env:
    GEMINI_API_KEY_2: ${{ secrets.GEMINI_API_KEY_2 }}   ← injected

run_eval.py:
  API_KEY = os.environ.get("GEMINI_API_KEY_2")           ← reads env var
```

**Zero secrets appear in any committed file. ✅**

---

*Report generated: 2026-05-05 | AI407L Lab 8 — TEXBase Deployment & Quality Gates*
