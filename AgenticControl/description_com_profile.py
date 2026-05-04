import requests
import google.generativeai as genai
import os
from dotenv import load_dotenv

# ── Configuration ────────────────────────────────────────────────────────
# In a real app, load these from your .env file
env_address = os.path.join(os.environ.get('WORKSPACE_ROOT', os.path.join(os.environ.get('WORKSPACE_ROOT', '.'), 'backend/.env'))
load_dotenv(dotenv_path=env_address)

# Now it will successfully find your keys!
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
JINA_API_KEY = os.environ.get("JINA_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)

def scrape_website_to_markdown(url: str) -> str:
    """
    Uses Jina Reader API to cleanly extract text from any URL.
    It automatically strips out ads, navbars, and messy HTML.
    """
    print(f"🕵️‍♂️ Scraping {url}...")
    jina_url = f"https://r.jina.ai/{url}"
    
    headers = {
        # This passes your API key securely to Jina's servers
        "Authorization": f"Bearer {JINA_API_KEY}",
        "X-Retain-Images": "none" 
    }
    
    response = requests.get(jina_url, headers=headers)
    
    if response.status_code == 200:
        return response.text
    else:
        raise Exception(f"Failed to scrape website. Status code: {response.status_code}\nResponse: {response.text}")

def generate_interview_answer(company_text: str, company_website: str, max_chars: int = 10000) -> str:
    """
    Feeds the scraped text into the LLM with a highly specific prompt.
    Safely truncates the text to avoid API Quota limit errors.
    """
    # 👇 THE FIX: Chop off the excess text
    if len(company_text) > max_chars:
        print(f"✂️ Truncating scraped text from {len(company_text)} to {max_chars} characters...")
        company_text = company_text[:max_chars]
        
    print("🧠 Synthesizing data and drafting answer...")
    
    # Initialize the model 
    model = genai.GenerativeModel('gemini-flash-lite-latest')
    
    prompt = f"""
    You are an intelligent, well-prepared job bot for {company_website}.
    
    I am going to provide you with the scraped text from their official website. 
    Based ONLY on this text, I want you to answer the classic question: 
    "What things company working on and what is their mission? What is their focus and what is there vision?"
    
    Guidelines for your answer:
    1. Keep it conversational, confident, and professional (around 3-4 short paragraphs).
    2. Identify their core product/service and who their target audience is.
    3. Highlight their overarching mission or the main problem they are trying to solve.
    4. Mention any recent milestones, unique features, or company values explicitly stated in the text.
    5. Do not hallucinate external information. If a detail isn't in the text, don't invent it.
    
    Here is the company website text:
    -----------------------------------
    {company_text}
    """
    
    response = model.generate_content(prompt)
    return response.text

# ── Execution ────────────────────────────────────────────────────────
# if __name__ == "__main__":
#     # Example Target
#     target_url = "https://www.anthropic.com" # Try changing this to another company!
#     company_name = "Anthropic"
    
#     try:
#         # Step 1: Get the data
#         raw_markdown = scrape_website_to_markdown(target_url)
        
#         # 👇 NEW: Print the exact text pulled by the scraper
#         print("\n" + "="*50)
#         print("📄 RAW SCRAPED DATA (From Jina):")
#         print("="*50 + "\n")
#         print(raw_markdown) 
#         print("\n" + "="*50 + "\n")
        
#         # Step 2: Generate the answer
#         answer = generate_interview_answer(raw_markdown, company_name)
        
#         # Step 3: Output
#         print("\n==========================================")
#         print(f"🎙️ INTERVIEW QUESTION: What do you know about {company_name}?")
#         print("==========================================\n")
#         print(answer)
        
#     except Exception as e:
#         print(f"❌ An error occurred: {e}")