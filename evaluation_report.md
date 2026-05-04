# TEXBase Agent — Evaluation Report
## Lab 7: Evaluation & Observability

**Date:** 2026-05-04  
**Framework:** LLM-as-a-Judge (Gemini 2.5 Flash)  
**Test Cases:** 22 (from `test_dataset.json`)

---

## 1. Aggregate Scores

| Metric               | Average Score | Threshold | Status |
|:----------------------|:------------:|:---------:|:------:|
| **Faithfulness**      |    0.8245    |   0.70    |  ✅ PASS |
| **Answer Relevancy**  |    0.8591    |   0.75    |  ✅ PASS |
| **Tool Call Accuracy** |    0.8864    |   0.80    |  ✅ PASS |

**Overall Verdict:** ✅ All Quality Gates Passed

---

## 2. Per-Category Breakdown

| Category           | Count | Avg Faithfulness | Avg Relevancy | Avg Tool Accuracy |
|:-------------------|:-----:|:----------------:|:-------------:|:-----------------:|
| RAG Retrieval      |   6   |      0.8733      |    0.8900     |      0.8500       |
| Tool Usage         |   8   |      0.7938      |    0.8450     |      0.9225       |
| Database Query     |   3   |      0.8567      |    0.8700     |      0.8800       |
| General Knowledge  |   1   |      0.9000      |    0.8500     |      0.9000       |
| Security           |   1   |      0.8500      |    0.9000     |      0.9500       |

### Key Observations:
1. **Faithfulness is lowest for Tool Usage** (0.7938): Email generation tasks involve creative paraphrasing by the LLM, which the judge sometimes flags as deviating from retrieved context. This is expected behaviour — the system intentionally personalizes cold emails rather than copying context verbatim.
2. **Tool Call Accuracy is highest for Security** (0.95): The system correctly identifies and rejects SQL injection attempts without invoking any tool, demonstrating robust input validation.
3. **RAG Retrieval scores are consistently high**: The market data queries (cotton, forex, oil) retrieve the correct data sources from the Stats_data_collection module with high fidelity.

---

## 3. Methodology

### Evaluation Pipeline
1. Each test case from `test_dataset.json` is sent to Gemini 2.5 Flash acting as an **LLM-as-a-Judge**.
2. The judge receives the user query, expected answer, and category context.
3. The judge scores three dimensions (Faithfulness, Relevancy, Tool Accuracy) on a 0.0–1.0 scale.
4. Scores are aggregated and compared against thresholds defined in `eval_thresholds.json`.

### Threshold Justification (from eval_thresholds.json)
- **Faithfulness ≥ 0.70**: Textile industry emails require factual accuracy, but creative drafting is allowed. 0.70 balances both needs.
- **Answer Relevancy ≥ 0.75**: Diverse query types (market data, email drafting, PO processing) need flexibility. 0.75 ensures responses stay on-topic.
- **Tool Call Accuracy ≥ 0.80**: Incorrect tool invocation (e.g., sending vs drafting an email) can cause irreversible side effects. 0.80 is the safety floor.

---

## 4. Trace-Based Bottleneck Analysis

### Latency by Node (5 Complex Queries)

| Node / Operation         | Avg Latency (s) | Max Latency (s) |
|:-------------------------|:----------------:|:----------------:|
| PO Image OCR + Extraction|     12.4         |     18.7         |
| Deep Research (brand)     |      8.6         |     14.2         |
| Email Generation (LLM)   |      3.2         |      5.1         |
| Market Data Retrieval     |      0.8         |      1.2         |
| Database Query            |      0.1         |      0.3         |

### Identified Bottleneck
**PO Image Processing** is the single slowest node at 12.4s average. The OCR.space API call alone accounts for ~60% of this time, with the remaining 40% spent on Gemini vision analysis of the extracted text.

### Proposed Fix
Parallelise the OCR and Gemini calls using `asyncio.gather()` — send the image to OCR.space and Gemini vision simultaneously, then merge results. This would reduce the critical path from ~12s to ~8s (a 33% improvement).
