import os
import re
import argparse
import datetime
from fpdf import FPDF
from google import genai

# 1. Initialize the Gemini Client

client = genai.Client(api_key="AIzaSyBk2-1rHDmRgKKW5WfLQ5T1tcL38jPmJAc")

# 2. Define your specific research prompts
DEFAULT_PROMPTS = {
    # "1. Consumer Fashion to Raw Material Translation": """
    #     Conduct deep market research across top global fashion websites, digital lookbooks, and retail trend reports (e.g., WWD, Vogue Business, major retail catalogs). 
    #     Do not just list styles; explicitly identify the specific textiles, fabric blends, and physical textures currently dominating collections. 
    #     Extract actionable data on what raw materials (e.g., heavyweight cotton, linen blends, specific synthetics) are driving consumer apparel preferences.
    # """
    "2. B2B Textile & Material Innovation": """
        Investigate the B2B textile market for current material innovations and commercial fiber developments. 
        Focus heavily on the adoption of sustainable fabrics, recycled blends, and technical/performance textiles (e.g., moisture-wicking, temperature-regulating). 
        Cite specific yarn and fabric types that are currently experiencing the highest sourcing demand from global brands.
    """
    # "3. South Asian Export Dynamics to the USA": """
    #     Analyze the current textile and apparel export data specifically from Pakistan, India, and Bangladesh to the USA. 
    #     Break down the top product categories (e.g., denim, knitwear, home textiles) successfully exported by each specific country. 
    #     Include recent volume statistics, current trade policies/tariffs affecting these regions, and how these three countries compete in fulfilling US import demands.
    # """,
    # "4. Manufacturing & Tech Advancements": """
    #     Research newly developed machinery and technological advancements in the physical textile manufacturing sector. 
    #     Cover concrete innovations in spinning, weaving, and dyeing processes (such as waterless dyeing, AI-driven automated quality control, or energy-efficient looms). 
    #     Summarize hot industry news regarding how modern manufacturing facilities are upgrading their hardware.
    # """,
    # "5. Actionable B2B Strategy & Outreach": """
    #     Synthesize current textile trends, South Asian trade dynamics, and machinery advancements into actionable strategic advice for a textile manufacturer or sourcing brokerage. 
    #     Detail exactly how they should evolve their manufacturing capabilities, which export certifications are currently most valuable for the US market, and how to adapt their digital marketing and client discovery strategies to secure new international buyers.
    # """
}


def clean_markdown_for_pdf(text):
    """Removes markdown formatting and strips all source/citation references."""
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)   # Remove bold **
    text = re.sub(r'\*(.*?)\*', r'\1', text)        # Remove italic *
    text = re.sub(r'#+(.*?)\n', r'\1\n', text)      # Remove markdown headers #

    # Remove inline citation brackets like [1], [2], [1, 2], [12], etc.
    text = re.sub(r'\[\d+(?:,\s*\d+)*\]', '', text)

    # Remove any Sources / References / Bibliography section at the end
    # Matches common headings regardless of case or leading #
    text = re.sub(
        r'\n\s*(?:#{1,3}\s*)?(?:Sources|References|Bibliography|Works Cited|Citations|Further Reading)'
        r'.*',
        '',
        text,
        flags=re.IGNORECASE | re.DOTALL
    )

    return text.strip()


def generate_deep_research_report(custom_query: str = None, topic: str = "Textile_Report"):
    # Base directory is the folder where this script lives
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join("/Volumes/ssd2/TEXBASE/src/ResearchAgent/", "research_pdf")
    os.makedirs(output_dir, exist_ok=True)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    print("Starting Deep Research Agent. This will take several minutes per section...\n")

    if custom_query:
        prompts = {topic: custom_query}
    else:
        prompts = DEFAULT_PROMPTS

    for section_title, prompt in prompts.items():
        print(f"\n{'='*50}")
        print(f"-> Initiating Research for: {section_title}")
        print(f"{'='*50}\n")

        # Call the Interactions API using the Deep Research Agent
        stream = client.interactions.create(
            input=prompt,
            agent="deep-research-pro-preview-12-2025",
            background=True,
            stream=True,
            agent_config={
                "type": "deep-research",
                "thinking_summaries": "auto"
            }
        )

        interaction_id = None
        section_text = ""

        # Process the stream
        for chunk in stream:
            if chunk.event_type == "interaction.start":
                interaction_id = chunk.interaction.id
                print(f"[System] Interaction started: {interaction_id}")

            elif chunk.event_type == "content.delta":
                # Capture the actual report text
                if chunk.delta.type == "text":
                    section_text += chunk.delta.text

                # Print the agent's thought process to the console
                elif chunk.delta.type == "thought_summary":
                    print(f"Thought: {chunk.delta.content.text}", flush=True)

            elif chunk.event_type == "interaction.complete":
                print(f"\n[System] Research Complete for {section_title}")

        # Add the compiled research to the PDF
        pdf.add_page()

        # Write Section Header
        pdf.set_font("helvetica", style="B", size=16)
        pdf.cell(0, 10, txt=section_title, ln=True, align='L')
        pdf.ln(5)

        # Write Research Body
        pdf.set_font("helvetica", size=11)
        clean_text = clean_markdown_for_pdf(section_text)

        # Handle potential encoding issues with FPDF by replacing unmappable chars
        safe_text = clean_text.encode('latin-1', 'replace').decode('latin-1')
        pdf.multi_cell(0, 6, txt=safe_text)

    # Save the final PDF inside research_pdf/
    safe_topic = re.sub(r'[^A-Za-z0-9_\-]', '_', topic)
    file_path = os.path.join(output_dir, f"{safe_topic}.pdf")
    pdf.output(file_path)

    print(f"\n{'='*50}")
    print(f"Success! Full deep research report saved to: {file_path}")
    print(f"{'='*50}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Deep Research Agent")
    parser.add_argument("--query", type=str, help="Custom research query to extract")
    parser.add_argument("--topic", type=str, default="Deep_Research_Textile_Report", help="Short specific topic name used for the output filename")
    args = parser.parse_args()

    generate_deep_research_report(custom_query=args.query, topic=args.topic)
    
    # Force exit to kill lingering Gemini Interaction background threads so Superagent unblocks
    os._exit(0)
