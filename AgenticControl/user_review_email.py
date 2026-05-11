import sqlite3
import json
import os
from dotenv import load_dotenv
from groq import Groq
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage as AzureSystemMessage, UserMessage as AzureUserMessage
from azure.core.credentials import AzureKeyCredential

# --- SETUP & CONSTANTS ---
ROOT_DIR = os.environ.get('WORKSPACE_ROOT', '.')
load_dotenv(dotenv_path=os.path.join(ROOT_DIR, 'backend/.env'))

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DB_TRACKING  = os.path.join(ROOT_DIR, 'Database/EmailsUnderReview/emailsUnderReview.db')

# Sender identity (same as EmailGenerator.py)
SENDER = {
    "company": "Arooj Enterprises",
    "name":    "Asad Irfan",
    "title":   "Senior Marketing Manager",
    "website": "www.texbase.com",
    "certs":   "ISO 14001, SEDEX, and OEKO-TEX",
    "capacity": "150,000 units/month",
}


def dict_factory(cursor, row):
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — Use Groq to turn short user feedback into detailed rewrite instructions
# ─────────────────────────────────────────────────────────────────────────────
def enhance_feedback_with_groq(raw_feedback: str, company_name: str) -> str:
    """Expands short user feedback into detailed rewriting instructions for a B2B textile cold email."""
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not found.")

    client = Groq(api_key=GROQ_API_KEY)

    prompt = f"""You are an expert B2B sales email coach specialising in textile/apparel manufacturing outreach.

    A Senior Marketing Manager at Arooj Enterprises (a Pakistan-based garment manufacturer) has written a cold email
    to {company_name}, a US apparel import buyer. The user wants to revise it based on this feedback:
    
    User feedback: "{raw_feedback}"
    
    Note: The feedback may contain context tags like [ROLE: Senior Marketing Manager] or [FOCUS: Concise, Professional]. 
    Strictly respect these strategic constraints in your instructions.
    
    Transform this into clear, detailed, professional rewriting instructions for an AI copywriter.
    Focus on tone, structure, persuasion, and textile industry context.
    Do NOT write the email itself. Output ONLY the detailed revision instructions."""

    response = client.chat.completions.create(
        messages=[
            {"role": "system", "content": "You are an instruction enhancer for B2B sales emails. Output only the enhanced instructions."},
            {"role": "user",   "content": prompt}
        ],
        model="llama-3.1-8b-instant",
        temperature=0.5,
        max_tokens=2000
    )
    return response.choices[0].message.content.strip()


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — Mistral rewrites the email using full outreach context from DB
# ─────────────────────────────────────────────────────────────────────────────
def refine_email_with_ai(current_body: str, enhanced_feedback: str, outreach: dict) -> str:
    """Rewrites the cold email using the rich outreach context stored in the tracking DB."""
    if not GITHUB_TOKEN:
        raise ValueError("GITHUB_TOKEN not found.")

    client = ChatCompletionsClient(
        endpoint="https://models.github.ai/inference",
        credential=AzureKeyCredential(GITHUB_TOKEN),
    )

    company_name  = outreach.get("company_name", "the company")
    hs_codes      = outreach.get("hs_codes", "N/A")
    top_suppliers = outreach.get("top_suppliers", "N/A")
    shipments     = outreach.get("total_shipments", "N/A")
    executives    = outreach.get("key_executives", "N/A")
    description   = outreach.get("company_description", "N/A")
    address       = outreach.get("address", "USA")
    company_email = outreach.get("company_email", "not updated")
    orig_subject  = outreach.get("generated_subject", "")
    deep_research = outreach.get("deep_research", "")

    deep_research_section = f"""
═══ DEEP RESEARCH INTEL (use this to sharpen specifics) ═══
{deep_research}
""" if deep_research else ""

    prompt = f"""You are an expert B2B sales email copywriter for the textile/apparel manufacturing industry.

═══ CONTEXT: WHO WE ARE EMAILING ═══
- Company       : {company_name}
- Location      : {address}
- Total Imports : {shipments} shipments
- HS Codes      : {hs_codes}
- Top Suppliers : {top_suppliers}
- Key Executives: {executives}
- Profile       : {description}
{deep_research_section}
═══ OUR COMPANY (THE SENDER) ═══
- {SENDER['company']} — {SENDER['title']}: {SENDER['name']}
- Capacity: {SENDER['capacity']} | Certs: {SENDER['certs']}
- Website: {SENDER['website']}

═══ CURRENT EMAIL DRAFT ═══
Subject: {orig_subject}
{current_body}

═══ REVISION INSTRUCTIONS ═══
{enhanced_feedback}

CRITICAL OUTPUT REQUIREMENTS:
- Rewrite the email applying ALL revision instructions above.
- Adopt a direct, professional Marketing Manager tone. No fluff. No generic openers.
- Keep all specific references to the recipient's HS codes, shipment volume, or executives.
- Sign off as: {SENDER['name']} | {SENDER['title']} | {SENDER['company']} | {SENDER['website']}
- Output ONLY the revised email ("Subject: ..." first line, then blank line, then body).
- Do NOT use markdown code blocks.
- Do NOT use placeholders like [Name]."""

    response = client.complete(
        messages=[
            AzureSystemMessage("You are an expert B2B textile cold email rewriter. Follow revision instructions precisely."),
            AzureUserMessage(prompt),
        ],
        temperature=0.7,
        top_p=1.0,
        max_tokens=1200,
        model="meta/Llama-3.3-70B-Instruct"
    )
    return response.choices[0].message.content.strip()


# ─────────────────────────────────────────────────────────────────────────────
# MAIN: Fetch → Enhance → Rewrite → Save
# ─────────────────────────────────────────────────────────────────────────────
def update_single_email(db_id: int, feedback: str):
    """Fetches tracking row by ID, rewrites with feedback, saves updated email back to DB."""

    if not os.path.exists(DB_TRACKING):
        print(f"❌ Database not found at {DB_TRACKING}")
        return

    with sqlite3.connect(DB_TRACKING) as conn:
        conn.row_factory = dict_factory
        cursor = conn.cursor()

        # 1. Fetch full tracking row (all outreach fields are now stored here)
        cursor.execute("SELECT * FROM tracking WHERE id = ?", (db_id,))
        row = cursor.fetchone()

        if not row:
            print(f"❌ No record found with ID: {db_id}")
            return

        company_name = row.get("company_name", "the company")

        # 2. Parse body_json to get current email draft
        try:
            payload       = json.loads(row["body_json"])
            current_email = payload["body"]["generated_content"]
        except (KeyError, json.JSONDecodeError) as e:
            print(f"❌ Could not parse body_json for ID {db_id}: {e}")
            return

        # 3. Build outreach context dict from the flat tracking row columns
        # Parse key_executives from JSON string to readable text
        raw_execs = row.get("key_executives", "")
        try:
            execs_list = json.loads(raw_execs) if raw_execs else []
            executives_text = ", ".join(
                f"{e.get('name','?')} ({e.get('title','?')})"
                for e in execs_list
            ) if execs_list else raw_execs
        except (json.JSONDecodeError, TypeError):
            executives_text = raw_execs  # already plain text

        # Read deep research report if it exists
        deep_research_text = ""
        research_path = row.get("deep_research_pdf", "")
        if research_path and os.path.exists(research_path):
            try:
                with open(research_path, "r", encoding="utf-8") as f:
                    deep_research_text = f.read()[:4000]  # cap at 4k chars
                print(f"📄 Loaded deep research: {os.path.basename(research_path)}")
            except Exception as e:
                print(f"⚠️  Could not read research file: {e}")

        outreach = {
            "company_name":        row.get("company_name", ""),
            "company_email":       row.get("company_email", "not updated"),
            "website":             row.get("website", ""),
            "address":             row.get("address", ""),
            "total_shipments":     row.get("total_shipments", ""),
            "top_suppliers":       row.get("top_suppliers", ""),
            "hs_codes":            row.get("hs_codes", ""),
            "company_description": row.get("company_description", ""),
            "key_executives":      executives_text,
            "generated_subject":   row.get("generated_subject", ""),
            "deep_research":       deep_research_text,
        }

        # 4. Enhance feedback with Groq
        print(f"🧠 [Step 1] Expanding feedback with Groq (Llama 3)...")
        try:
            detailed_instructions = enhance_feedback_with_groq(feedback, company_name)
            print(f"📝 Enhanced instructions:\n{detailed_instructions}\n")
        except Exception as e:
            print(f"❌ Groq error: {e}")
            return

        # 5. Rewrite with Mistral using full outreach context
        print(f"🤖 [Step 2] Rewriting email with Mistral AI...")
        try:
            new_email = refine_email_with_ai(current_email, detailed_instructions, outreach)
        except Exception as e:
            print(f"❌ Mistral error: {e}")
            return

        # 6. Extract Subject and Body from AI output
        new_subject = payload["body"].get("subject", row.get("generated_subject", ""))
        new_body_text = new_email
        
        if new_email.lower().startswith("subject:"):
            parts = new_email.split("\n\n", 1)
            new_subject = parts[0][8:].strip() # remove 'Subject:'
            new_body_text = parts[1].strip() if len(parts) > 1 else new_email

        # 7. Update JSON structure preserving outreach_data
        payload["body"]["generated_content"] = new_body_text
        payload["body"]["subject"] = new_subject
        
        # 8. Save updated email back into DB (both JSON and root column)
        cursor.execute(
            "UPDATE tracking SET body_json = ?, generated_subject = ? WHERE id = ?",
            (json.dumps(payload), new_subject, db_id)
        )
        conn.commit()

        print(f"\n✅ ID {db_id} updated successfully!\n")
        print("─" * 60)
        print(new_email)
        print("─" * 60)
        return new_body_text, new_subject


# ─────────────────────────────────────────────────────────────────────────────
# Run
# ─────────────────────────────────────────────────────────────────────────────
# if __name__ == "__main__":
#     target_id    = 1
#     user_feedback = "make it more concise and punchy, reduce to 3 paragraphs, be more direct about our capacity advantage"

#     update_single_email(db_id=target_id, feedback=user_feedback)