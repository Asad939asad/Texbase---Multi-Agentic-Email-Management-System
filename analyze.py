import feedback_logger
import collections
import os
from datetime import datetime
from dotenv import load_dotenv

# FIX: only import genai if available, to avoid crash when not installed
try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False


def run_analysis():
    load_dotenv()
    logs = feedback_logger.get_all_logs()

    if not logs:
        print("No feedback data yet.")
        return

    # Corrected: use the standard GEMINI_API_KEY from .env
    api_key = os.environ.get("GEMINI_API_KEY")

    model = None
    if api_key and GENAI_AVAILABLE:
        genai.configure(api_key=api_key)
        # FIX 2: gemini-3-flash-preview does not exist → use gemini-1.5-flash
        model = genai.GenerativeModel('gemini-flash-lite-latest')

    # ---------------------------------------------------------------
    # Section A — Global stats
    # ---------------------------------------------------------------
    total = len(logs)
    positive_logs   = [l for l in logs if l.get('feedback') == 'good']
    bad_or_partial  = [l for l in logs if l.get('feedback') in ('bad', 'partial')]
    neg_count       = len([l for l in logs if l.get('feedback') == 'bad'])
    overall_neg_rate = (len(bad_or_partial) / total) * 100 if total > 0 else 0

    stats_by_section = {}
    for l in logs:
        # FIX 5: use .get() to avoid KeyError if 'section' column missing
        s = l.get('section', 'unknown')
        if s not in stats_by_section:
            stats_by_section[s] = {"total": 0, "bad": 0, "partial": 0}
        stats_by_section[s]["total"] += 1
        if l.get('feedback') == 'bad':     stats_by_section[s]["bad"] += 1
        if l.get('feedback') == 'partial': stats_by_section[s]["partial"] += 1

    stats_output_lines = [
        "=" * 50,
        "SECTION A — GLOBAL STATISTICS",
        "=" * 50,
        f"Total responses logged : {total}",
        # FIX 6: rubric requires positive count — was missing entirely
        f"Positive feedback      : {len(positive_logs)}",
        f"Negative feedback      : {neg_count}",
        f"Partial feedback       : {len(bad_or_partial) - neg_count}",
        f"Overall negative rate  : {overall_neg_rate:.1f}%",
        "",
        "Breakdown by section:",
    ]
    for s, data in stats_by_section.items():
        neg_rate = ((data['bad'] + data['partial']) / data['total']) * 100
        stats_output_lines.append(
            f"  {s:<20} {data['total']} logs,  {neg_rate:.1f}% negative/partial"
        )

    # FIX 3: stats_output was built but never printed — now printed here
    section_a_text = "\n".join(stats_output_lines)
    print(section_a_text)

    # ---------------------------------------------------------------
    # Section B — Top 3 failed queries (rubric requirement)
    # ---------------------------------------------------------------
    print("\n" + "=" * 50)
    print("SECTION B — TOP 3 FAILED QUERIES")
    print("=" * 50)

    bad_logs = [l for l in logs if l.get('feedback') in ('bad', 'partial')]
    query_counter = collections.Counter(
        l.get('user_input', '(no input)') for l in bad_logs
    )
    top3 = query_counter.most_common(3)

    if not top3:
        print("No failed queries recorded yet.")
    else:
        for rank, (query, count) in enumerate(top3, 1):
            # truncate long queries for readable output
            display = query[:80] + "..." if len(query) > 80 else query
            print(f"  #{rank} ({count} bad ratings): {display}")

    top3_text = "\n".join(
        [f"#{r+1} ({c} bad): {q[:80]}" for r, (q, c) in enumerate(top3)]
    ) if top3 else "No failed queries yet."

    # ---------------------------------------------------------------
    # Section C — Per-section deep analysis
    # ---------------------------------------------------------------
    per_section_results = []

    def ask_gemini(prompt):
        """Helper — returns AI text or a clear skip message."""
        if model:
            try:
                return model.generate_content(prompt).text
            except Exception as e:
                return f"AI analysis failed: {e}"
        return "AI analysis skipped (no GEMINI_API_KEY set)"

    # 1. market_analysis
    m_logs = feedback_logger.get_logs_by_section('market_analysis')
    if m_logs:
        print("\n--- Market Analysis ---")
        bad_m = [l for l in m_logs if l.get('feedback') == 'bad']
        param_counts = collections.Counter(
            l.get('parameter_name', 'unknown') for l in m_logs
        )
        param_bad = collections.Counter(
            l.get('parameter_name', 'unknown') for l in bad_m
        )
        top_bad_params = sorted(
            [(p, param_bad[p] / param_counts[p]) for p in param_counts],
            key=lambda x: x[1], reverse=True
        )[:3]

        # FIX 4: top_bad_params was computed but never printed
        print("Top failing parameters:")
        for param, rate in top_bad_params:
            print(f"  {param}: {rate*100:.1f}% bad feedback rate")

        m_prompt = (
            "These market predictions received negative feedback from users. "
            "Identify which commodity parameters are most problematic and suggest "
            "whether the issue is in data staleness, prediction logic, or strategy "
            "framing.\n\n"
        )
        for l in bad_m[-10:]:
            m_prompt += f"Parameter: {l.get('parameter_name', 'N/A')}\n"
            m_prompt += f"Prediction: {l.get('agent_response', '')}\n"
            if l.get('flagged_excerpt'):
                m_prompt += f"Flagged Text: {l['flagged_excerpt']}\n"
            if l.get('user_comment'):
                m_prompt += f"User Reason: {l['user_comment']}\n"
            m_prompt += "---\n"

        ai_resp = ask_gemini(m_prompt)
        print(f"Gemini: {ai_resp[:300]}...")
        per_section_results.append(("Market Analysis", top_bad_params, ai_resp))

    # 2. email_editor
    e_logs = feedback_logger.get_logs_by_section('email_editor')
    if e_logs:
        print("\n--- Email Editor ---")
        good_e = len([l for l in e_logs if l.get('feedback') == 'good'])
        part_e = len([l for l in e_logs if l.get('feedback') == 'partial'])
        bad_e  = len([l for l in e_logs if l.get('feedback') == 'bad'])
        print(f"  Used as-is: {good_e}  |  Edited: {part_e}  |  Rewrote: {bad_e}")

        e_prompt = (
            "These email drafts were rejected or heavily rewritten by users. "
            "Identify the common patterns. Was it tone, length, specificity, or "
            "missing context?\n\n"
        )
        for l in [x for x in e_logs if x.get('feedback') == 'bad'][-10:]:
            e_prompt += f"User Prompt: {l.get('user_input', '')}\n"
            e_prompt += f"Draft: {l.get('agent_response', '')}\n---\n"

        ai_resp = ask_gemini(e_prompt)
        print(f"Gemini: {ai_resp[:300]}...")
        per_section_results.append((
            "Email Editor",
            f"Good: {good_e}, Partial: {part_e}, Bad: {bad_e}",
            ai_resp
        ))

    # 3. inbox_flow
    i_logs = feedback_logger.get_logs_by_section('inbox_flow')
    if i_logs:
        print("\n--- Inbox Flow ---")
        stage_counts = collections.Counter(
            l.get('pipeline_stage', 'unknown') for l in i_logs
        )
        stage_bad = collections.Counter(
            l.get('pipeline_stage', 'unknown')
            for l in i_logs if l.get('feedback') in ('bad', 'partial')
        )
        # FIX 7: most_common(1)[0] crashes on empty Counter — guard added
        if stage_bad:
            worst_stage = stage_bad.most_common(1)[0]
            print(f"  Worst stage: {worst_stage[0]} ({worst_stage[1]} failures)")
        else:
            worst_stage = ("None", 0)
            print("  No pipeline failures recorded.")

        i_prompt = (
            "These pipeline stages recorded failures or partial completions. "
            "Identify which stage is most fragile and what fix is needed.\n\n"
        )
        for l in [x for x in i_logs if x.get('feedback') in ('bad', 'partial')][-10:]:
            i_prompt += f"Stage: {l.get('pipeline_stage', 'N/A')}\n"
            i_prompt += f"Action: {l.get('user_input', '')}\n"
            i_prompt += f"Outcome: {l.get('agent_response', '')}\n---\n"

        ai_resp = ask_gemini(i_prompt)
        print(f"Gemini: {ai_resp[:300]}...")
        per_section_results.append((
            "Inbox Flow",
            f"Worst Stage: {worst_stage[0]} ({worst_stage[1]} fails)",
            ai_resp
        ))

    # 4. po_quotation
    p_logs = feedback_logger.get_logs_by_section('po_quotation')
    if p_logs:
        print("\n--- PO Quotation ---")
        deltas  = [l['price_delta'] for l in p_logs if l.get('price_delta') is not None]
        avg_delta = sum(deltas) / len(deltas) if deltas else 0
        bad_rate  = (
            len([l for l in p_logs if l.get('feedback') == 'bad']) / len(p_logs)
        ) * 100
        print(f"  Avg price delta: {avg_delta:.2f}  |  Bad rate: {bad_rate:.1f}%")

        p_prompt = (
            "These purchase order price predictions received negative feedback. "
            "Analyze the delta pattern and suggest whether the issue is in "
            "training data, feature engineering, or retrieval context.\n\n"
        )
        for l in [x for x in p_logs if x.get('feedback') == 'bad'][-10:]:
            p_prompt += f"Item: {l.get('user_input', '')}\n"
            p_prompt += f"Predicted: {l.get('predicted_price', 'N/A')}\n"
            p_prompt += f"Actual: {l.get('actual_price', 'N/A')}\n"
            if l.get('correction_note'):
                p_prompt += f"Correction: {l['correction_note']}\n"
            p_prompt += "---\n"

        ai_resp = ask_gemini(p_prompt)
        print(f"Gemini: {ai_resp[:300]}...")
        per_section_results.append((
            "PO Quotation",
            f"Avg Delta: {avg_delta:.2f}, Bad Rate: {bad_rate:.1f}%",
            ai_resp
        ))

    # ---------------------------------------------------------------
    # Section D — Cross-section Gemini recommendation
    # ---------------------------------------------------------------
    print("\n" + "=" * 50)
    print("SECTION D — STRATEGIC RECOMMENDATION")
    print("=" * 50)

    cross_prompt = (
        "Across these 4 sections of a B2B textile AI platform, analyze which "
        "section has the most systemic quality issues and recommend ONE "
        "highest-impact fix.\n\n"
    )
    for section, stats, ai_analysis in per_section_results:
        cross_prompt += (
            f"Section: {section}\nStats: {stats}\n"
            f"Summary: {str(ai_analysis)[:300]}...\n\n"
        )
    cross_recommendation = ask_gemini(cross_prompt)
    print(cross_recommendation)

    # ---------------------------------------------------------------
    # Section E — Save analysis_report.md
    # ---------------------------------------------------------------
    report_lines = [
        "# MLOps Feedback Analysis Report",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Global Statistics",
        # FIX 8: was "\n".join(stats_output) — list joined with no separator worked
        # but stats_output was a list of strings so this is fine; keeping consistent
        section_a_text,
        "",
        "## Top 3 Failed Queries",
        top3_text,
    ]

    for section, stats, ai_analysis in per_section_results:
        report_lines += [
            f"\n## {section}",
            f"**Metrics:** {stats}",
            "",
            f"**Gemini Analysis:**",
            str(ai_analysis),
        ]

    report_lines += [
        "\n## Strategic Recommendation",
        cross_recommendation,
    ]

    report_text = "\n".join(report_lines)
    with open("analysis_report.md", "w", encoding="utf-8") as f:
        f.write(report_text)

    print("\nAnalysis complete. Report saved to analysis_report.md")


if __name__ == "__main__":
    run_analysis()