import os
import json
import re
from dotenv import load_dotenv
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.environ.get('WORKSPACE_ROOT', '.'), 'backend/.env'))

# Get GitHub token instead of Gemini API key
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

company_profile="""Company Overview: Arooj Enterprises
Established in 1993, Arooj Enterprises is a progressive and innovative manufacturing company specializing in the production and export of knitted and fashion garments. With over 28 years of industry experience, the company has built a strong global footprint by supplying high-quality apparel—including sporting goods—to clients around the world at economical prices.

Core Operations and Capabilities
Product Range: The company manufactures everything from basic knitted items to highly fashioned, complex garments.

Custom Development: Arooj Enterprises excels at turning clients' conceptual ideas into tangible reality. They achieve this by combining skilled manpower, deep product knowledge, and top-tier technology.

Global Export: They maintain excellent, highly satisfying relationships with an international clientele, driven by a reputation for quality products and prompt, friendly service.

Vision and Mission
Vision: The company aims to achieve market leadership by offering an unmatched, diverse, and exclusive product mix. They strive to operate using world-class systems while maintaining the highest ethical and professional standards.

Mission: The ultimate goal is customer satisfaction at the highest level. This is accomplished through a combination of technological excellence, extensive industry experience, and a success-oriented mindset.

Corporate Values and Leadership
Active Leadership: The Chairman is deeply integrated into every aspect of the organization, driving a culture of hard work, dedication, and continuous improvement.

Employee Empowerment: Arooj Enterprises believes in enacting policies that directly benefit its workforce. This approach has fostered a highly devoted team that is proud to contribute to the company's persistent success.

Environmental Responsibility: Alongside employee welfare, the company is committed to operational policies that contribute to the betterment of the environment.

Future Outlook: Recognized for its reliability and high manufacturing standards, the company's leadership is committed to maintaining its quality while eagerly taking on new challenges to scale new heights in the future."""

# ── Sender (Arooj Enterprises) fixed profile ──────────────────────────────────
SENDER = {
    "company":   "Arooj Enterprises",
    "est":       "1993",
    "name":      "Asad Irfan",
    "title":     "Senior Marketing Manager",
    "website":   "www.texbase.com",
    "capacity":  "150,000 units/month",
    "certs":     "ISO 14001, SEDEX, and OEKO-TEX",
    "advantage": "vertical integration and rigorous quality control",
    "product_range": "knitted & woven garments, sportswear, fashion apparel, and basic basics",
    "countries_served": "USA, UK, EU, Australia",
}

def generate_cold_email(client_data: dict) -> str:
    """
    Generates a B2B cold outreach email from Arooj Enterprises to a US import buyer.
    client_data is one row from the outreach_companies DB table.
    Returns a formatted string: 'Subject: ...\n\n<body>'
    """
    if not GITHUB_TOKEN:
        print("Error: GITHUB_TOKEN not found in environment variables.")
        return "{}"

    # ── Initialize client ──────────────────────────────────────────────────────
    try:
        client = ChatCompletionsClient(
            endpoint="https://models.github.ai/inference",
            credential=AzureKeyCredential(GITHUB_TOKEN),
        )
    except Exception as e:
        print(f"Error initializing client: {e}")
        return "{}"

    # ── Build recipient context from DB fields ─────────────────────────────────
    company_name   = client_data.get("company_name", "the company")
    website        = client_data.get("website", "")
    address        = client_data.get("address", "")
    shipments      = client_data.get("total_shipments", "")
    suppliers      = client_data.get("top_suppliers", "")
    hs_codes       = client_data.get("hs_codes", "")
    description    = client_data.get("company_description", "")
    executives     = client_data.get("key_executives", "")
    email_addr     = client_data.get("email", "not updated")

    recipient_context = f"""
    - Company Name      : {company_name}
    - Website           : {website or 'N/A'}
    - Location          : {address or 'USA'}
    - Total Shipments   : {shipments or 'N/A'}
    - Known Suppliers   : {suppliers or 'N/A'}
    - HS Codes Imported : {hs_codes or 'N/A'}
    - Company Profile   : {description or 'N/A'}
    - Key Executives    : {executives or 'N/A'}
    """

    sender_context = f"""
    - Company    : {SENDER['company']} (Est. {SENDER['est']})
    - Contact    : {SENDER['name']}, {SENDER['title']}
    - Website    : {SENDER['website']}
    - Capacity   : {SENDER['capacity']}
    - Certifications : {SENDER['certs']}
    - Product Range  : {SENDER['product_range']}
    - Key Advantage  : {SENDER['advantage']}
    - Markets Served : {SENDER['countries_served']}
    """

    prompt = f"""
You are an expert B2B sales email writer for the textile manufacturing industry.

Write a highly targeted cold outreach email from a Pakistan-based garment manufacturer
(Arooj Enterprises) to a US-based apparel import company ({company_name}).

═══ RECIPIENT (US BUYER) ═══
{recipient_context}

═══ SENDER (OUR COMPANY) ═══
{sender_context}

INSTRUCTIONS — STRUCTURE & LENGTH (CRITICAL):
- Total length: 120 to 200 words. Skimmable, direct, no fluff.
- Exactly 4 short paragraphs:
  1. THE HOOK: Reference something specific about the recipient — their HS codes,
     known suppliers, shipment volume, or product category. Show you've done your homework.
     Do NOT open with "I hope this email finds you well" or "My name is...".
  2. THE FIT: Explain precisely why Arooj Enterprises is a natural supply chain fit
     for this buyer. Reference our capacity, certifications, and specific product range
     that matches their import profile. Be concrete, not generic.
  3. THE DIFFERENTIATOR: One sentence on vertical integration, quality control,
     or our Pakistan cost-to-quality advantage — whichever is most relevant to this buyer.
  4. THE CTA: A single, low-friction ask. (e.g. "Would a quick call this week make sense?"
     or "Happy to send samples and pricing — just say the word.")

INSTRUCTIONS — TONE:
- Professional, marketing-focused, and results-driven. Direct but collaborative.
- Avoid: "thrilled", "excited", "delve", "leverage", "synergy", "cutting-edge".
- Write as a company leader, not a marketing associate or an AI bot.
- Eliminate "robotic" openers; start with value, not pleasantries.
- If key executives are known, address the email to them by name.

INSTRUCTIONS — PERSONALISATION:
- Use the recipient's HS codes to name their actual product categories (e.g. "knitwear",
  "women's woven bottoms", "sportswear") rather than generic terms.
- If known suppliers are listed, briefly acknowledge the category they cover and
  position Arooj as a complementary or superior alternative.

CRITICAL OUTPUT REQUIREMENT:
- Output strictly valid JSON with exactly two keys: "subject" and "body".
- "subject": 5-8 word subject line. Direct and specific to their business, not clickbait.
  Example: "Pakistan knitwear supply — fits your HS 6110 imports"
- "body": Full email including greeting and sign-off with sender's name, title, website.
- THE BODY MUST INCLUDE \n\n (escaped newlines) BETWEEN EVERY PARAGRAPH. Do NOT output a single flat block of text!
- Sign off as: {SENDER['name']} | {SENDER['title']} | {SENDER['company']} | {SENDER['website']}
- Do NOT use placeholders like [Name] or [Link].
- Do NOT wrap JSON in markdown code blocks. Output ONLY the raw JSON object.
"""

    # ── Call the API ───────────────────────────────────────────────────────────
    try:
        response = client.complete(
            messages=[
                SystemMessage("You are an expert B2B textile sales email writer. Always return strictly valid JSON. No markdown wrappers."),
                UserMessage(prompt),
            ],
            temperature=0.75,
            top_p=1.0,
            max_tokens=1200,
            model="meta/Llama-3.3-70B-Instruct" 
        )

        content = response.choices[0].message.content.strip()

        # Robust JSON extraction
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            try:
                parsed  = json.loads(json_match.group(0))
                subject = parsed.get("subject", "Supply chain partnership — Arooj Enterprises")
                body    = parsed.get("body", "")
                return f"Subject: {subject}\n\n{body}"
            except json.JSONDecodeError:
                pass

        return content.replace('```json', '').replace('```', '').strip()

    except Exception as e:
        print(f"Error calling GitHub Models API: {e}")
        return "{}"


# ── Keep legacy function name as alias so existing callers don't break ─────────
def generate_application_body(company_data: dict, user_data: dict) -> str:
    """Legacy alias — maps old job-app call to new textile B2B email generator."""
    return generate_cold_email(company_data)

# ==========================================
# Quick Test — pulls first company from DB
# ==========================================
if __name__ == "__main__":
    import sqlite3
    ROOT_DIR = os.environ.get('WORKSPACE_ROOT', '.')
    DB_PATH = os.path.join(ROOT_DIR, 'Database/outreach_data/excel_data.db')
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM outreach_companies LIMIT 1").fetchone()
    conn.close()

    if not row:
        print("No companies in DB yet. Run Excel_Processor.py first.")
    else:
        client_data = dict(row)
        print(f"\n📨 Generating email for: {client_data.get('company_name')}\n")
        result = generate_cold_email(client_data)
        print("─" * 60)
        print(result)
        print("─" * 60)