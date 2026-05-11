# TEXBase Agent: Automated Quality Gates & CI/CD Report

## 1. Objective
To implement an automated evaluation pipeline that enforces quality standards on every code change. The pipeline ensures that the TEXBase multi-agent system maintains high standards for **Faithfulness**, **Answer Relevancy**, and **Tool Call Accuracy** before being deployed.

---

## 2. Threshold Configuration (`eval_thresholds.json`)
The following thresholds have been established as the "Quality Gate" criteria:

| Metric | Threshold | Justification |
| :--- | :--- | :--- |
| **Faithfulness** | 0.70 | Essential for market intelligence data (e.g., commodity prices). A lower value would risk business-critical hallucinations. |
| **Answer Relevancy** | 0.75 | Ensures queries about logistics and sourcing are addressed directly. A 10% lower value would allow too much "drift" in AI emails. |
| **Tool Call Accuracy** | 0.80 | High precision is required to avoid triggering irreversible actions (like sending an email) in the wrong context. |

---

## 3. Modular CI/CD Pipeline Configuration
The TEXBase system uses a multi-stage **GitHub Actions** pipeline (`.github/workflows/main.yml`) to enforce quality at different layers of the `AgenticControl` directory.

### Pipeline Jobs & Outcomes:

1. **Code Quality & Linting**: 
   - Scans all 28 Python scripts in `AgenticControl` for syntax errors and PEP8 compliance.
   - Ensures the codebase is maintainable and free of obvious bugs.

2. **AgenticControl Unit Validation**:
   - Executes targeted functional tests for core libraries:
     - **Excel_Processor**: Validates LLM-based column mapping logic.
     - **Email_sender**: Validates HTML formatting and SMTP security.
     - **PO_Processor**: Validates OCR field extraction reliability.

3. **Security & SQLi Audit**:
   - Performs a static scan to ensure no raw secrets (Gemini/Gmail keys) are committed.
   - Audits `personeldata.py` and `db_manager.py` to ensure all SQL queries are parameterized to prevent SQL injection.

4. **LLM Quality Gate (Headless Evaluation)**:
   - The final "Gate" that runs `run_eval.py`.
   - Uses **LLM-as-a-Judge** to evaluate RAG faithfulness and answer relevancy.
   - **Mandatory Outcome**: If any metric (Faithfulness < 0.70) fails, the entire build is blocked.

5. **Production Deployment**:
   - Triggered ONLY if all previous 4 jobs pass.
   - Protects the production environment from degraded agent performance.

---

## 4. Breaking Change Demonstration

### State A: Failed Build (Degraded Agent)
**Scenario**: The system prompt was intentionally modified to include "vague" instructions, and RAG context was disconnected.
- **Metric Result**: Faithfulness dropped to **0.421** (Threshold: 0.70).
- **Outcome**: CI Pipeline marked as **FAILED**.

```text
[CI Log Snapshot]
❌ Run Quality Gate Evaluation
   ...
   faithfulness         0.4210  (min: 0.70)  ❌ FAIL
   answer_relevancy     0.5120  (min: 0.75)  ❌ FAIL
   tool_call_accuracy   0.5850  (min: 0.80)  ❌ FAIL
   ======================================================================
   Overall: ❌ QUALITY GATE FAILED
   Error: Process completed with exit code 1.
```

### State B: Passed Build (Optimized Agent)
**Scenario**: Prompt logic was restored and vector database retrieval was optimized.
- **Metric Result**: All metrics surpassed thresholds (e.g., Faithfulness **0.942**).
- **Outcome**: CI Pipeline marked as **SUCCESS**.

```text
[CI Log Snapshot]
✅ Run Quality Gate Evaluation
   ...
   faithfulness         0.9420  (min: 0.70)  ✅ PASS
   answer_relevancy     0.8850  (min: 0.75)  ✅ PASS
   tool_call_accuracy   0.9100  (min: 0.80)  ✅ PASS
   ======================================================================
   Overall: ✅ ALL GATES PASSED
   Build Success: exit code 0.
```

---

## 5. Machine-Readable Results
The results are saved to `eval_results.json` after each run, enabling tracking of performance over time.

```json
{
  "timestamp": "2026-05-06T10:15:22.123456",
  "metrics": [
    { "name": "faithfulness", "score": 0.942, "passed": true },
    ...
  ],
  "overall_pass": true
}
```
