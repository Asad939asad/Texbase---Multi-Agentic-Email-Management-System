"""
Brand Data Extraction via Gemini API
Researches a US brand using Gemini with Google Search grounding.
Extracts products, key management contacts, and official website.
Saves results to SQLite database.
"""

import json
import sqlite3
import sys
import os
from google import genai
from google.genai import types


DB_PATH = os.path.join(os.environ.get('WORKSPACE_ROOT', '.'), 'Agentic_Directory/NordStorm_brandsData/nordstrom_brands.db')

client = genai.Client(api_key="AIzaSyD_YN1gB_YJluDtMOU2b4ED1xc1VHIWwY4")
google_search_tool = types.Tool(
    google_search=types.GoogleSearch()
)


def init_db():
    """Create the brands table if it doesn't exist."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS brand_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            brand_name TEXT UNIQUE NOT NULL,
            products_description TEXT,
            official_website TEXT,
            key_management TEXT,
            summary TEXT,
            search_sources TEXT,
            raw_response TEXT,
            error TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def save_to_db(result: dict):
    """Save a brand research result to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    brand_name = result.get("brand_name", "")
    key_mgmt = json.dumps(result.get("key_management", []), ensure_ascii=False)
    sources = json.dumps(result.get("search_sources", []), ensure_ascii=False)

    cursor.execute("""
        INSERT INTO brand_profiles (brand_name, products_description, official_website,
                                     key_management, summary, search_sources, raw_response, error)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(brand_name) DO UPDATE SET
            products_description = excluded.products_description,
            official_website = excluded.official_website,
            key_management = excluded.key_management,
            summary = excluded.summary,
            search_sources = excluded.search_sources,
            raw_response = excluded.raw_response,
            error = excluded.error,
            created_at = CURRENT_TIMESTAMP
    """, (
        brand_name,
        result.get("products_description", ""),
        result.get("official_website", ""),
        key_mgmt,
        result.get("summary", ""),
        sources,
        result.get("raw_response", ""),
        result.get("error", "")
    ))

    conn.commit()
    conn.close()
    print(f"[✓] Saved to DB: {brand_name}")


def research_brand(brand_name: str) -> dict:
    """
    Research a US brand using Gemini API with Google Search grounding.

    Args:
        brand_name: Name of the brand to research.

    Returns:
        Dictionary containing brand profile data.
    """
    prompt = f"""You are a business researcher.

Research the following US brand "{brand_name}" and provide:
1. The products or services they sell (brief description)
2. The names and contact information of key management (CEO, sourcing officers, owner, founders, or relevant leadership with LinkedIn or email if publicly available)
3. Their official website link

Only include accurate, publicly available information — nothing speculative.

CRITICAL: Every contact MUST have an email address. This is mandatory and non-negotiable.
- First, search for their publicly listed email.
- If not found, determine the company's email domain from their website, then predict the email using standard corporate patterns (e.g. first.last@domain.com, firstinitial.last@domain.com, first@domain.com).
- Also include general contact emails like info@domain.com, sales@domain.com if available.
- NEVER leave the email field empty.

RETURN ONLY RAW JSON matching this exact schema. No commentary, no markdown fences:
{{
  "brand_name": "{brand_name}",
  "products_description": "...",
  "official_website": "...",
  "key_management": [
    {{
      "name": "...",
      "title": "...",
      "linkedin": "...",
      "email": "REQUIRED - must not be empty"
    }}
  ],
  "summary": "..."
}}

For key_management, include as many people as you can find publicly. Every entry MUST have an email."""

    try:
        response = client.models.generate_content(
            model="gemini-3.1-pro-preview",
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[google_search_tool],
                response_modalities=["TEXT"]
            )
        )

        raw_text = response.text.strip()

        # Clean markdown fences if present
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        elif raw_text.startswith("```"):
            raw_text = raw_text[3:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]

        result = json.loads(raw_text.strip())

        # Attach grounding sources if available
        if (response.candidates
                and response.candidates[0].grounding_metadata
                and response.candidates[0].grounding_metadata.grounding_chunks):
            sources = []
            for chunk in response.candidates[0].grounding_metadata.grounding_chunks:
                try:
                    sources.append({"title": chunk.web.title, "uri": chunk.web.uri})
                except Exception:
                    pass
            if sources:
                result["search_sources"] = sources

        return result

    except json.JSONDecodeError:
        return {
            "brand_name": brand_name,
            "error": "Failed to parse Gemini response as JSON",
            "raw_response": response.text if response else ""
        }
    except Exception as e:
        return {
            "brand_name": brand_name,
            "error": str(e)
        }


if __name__ == "__main__":
    init_db()

    if len(sys.argv) > 1:
        name = " ".join(sys.argv[1:])
    else:
        name = "ZANEROBE"

    print(f"[*] Researching brand: {name}\n")
    result = research_brand(name)
    save_to_db(result)
    print(json.dumps(result, indent=2, ensure_ascii=False))
