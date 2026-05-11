import os
import json
import sys
import chromadb
from groq import Groq
from dotenv import load_dotenv

# Load env from backend/.env
ROOT_DIR = os.environ.get('WORKSPACE_ROOT', '.')
load_dotenv(os.path.join(ROOT_DIR, 'backend/.env'))

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
RISK_FACTORS_PATH = os.path.join(ROOT_DIR, 'Excel_Generator/Stats_data_collection/risk_factors.json')
DB_PATH = os.path.join(ROOT_DIR, 'Database/ChromaMarket')

def get_market_context():
    if not os.path.exists(RISK_FACTORS_PATH):
        return []
    
    with open(RISK_FACTORS_PATH, 'r') as f:
        data = json.load(f)
    
    chunks = []
    
    # 1. Strategic Analysis
    if data.get("llm_strategic_analysis"):
        chunks.append(f"Strategic Analysis: {data['llm_strategic_analysis']}")
    
    # 2. Data Snapshot (Prices)
    snap = data.get("data_snapshot", {})
    price_info = "Market Prices Snapshot:\n"
    for k, v in snap.items():
        if isinstance(v, (int, float)):
            price_info += f"- {k.replace('_', ' ').title()}: {v}\n"
    chunks.append(price_info)
    
    # 3. Regional Prices
    for key in ["tpa_regions", "eg_regions"]:
        if key in snap:
            region_info = f"Regional Prices ({key.replace('_', ' ').title()}):\n"
            for r in snap[key]:
                region_info += f"- {r['region']}: {r['price']} ({r['change']})\n"
            chunks.append(region_info)
            
    # 4. Alerts
    alerts = data.get("alerts", [])
    if alerts:
        alert_info = "Active Market Alerts:\n"
        for a in alerts:
            alert_info += f"- [{a.get('severity', 'INFO')}] {a.get('title')}: {a.get('message')}\n"
        chunks.append(alert_info)
        
    return chunks

def init_rag():
    try:
        client = chromadb.PersistentClient(path=DB_PATH)
        collection = client.get_or_create_collection(name="market_intelligence")
        
        chunks = get_market_context()
        if not chunks:
            return collection, False
        
        collection.add(
            documents=chunks,
            ids=[f"chunk_{i}" for i in range(len(chunks))]
        )
        return collection, True
    except Exception as e:
        print(f"⚠️ [RAG] Vector DB initialization failed (likely download timeout). Falling back to keyword search.")
        return None, False

def manual_retrieval(question, chunks):
    """Simple keyword-based retrieval as fallback for when embeddings fail."""
    # Score chunks based on word overlap
    q_words = set(question.lower().split())
    scored = []
    for chunk in chunks:
        c_words = set(chunk.lower().split())
        score = len(q_words.intersection(c_words))
        scored.append((score, chunk))
    
    # Sort by score descending
    scored.sort(key=lambda x: x[0], reverse=True)
    return [s[1] for s in scored[:3]]

def query_market(question):
    if not GROQ_API_KEY:
        return "Error: GROQ_API_KEY not found in environment."

    chunks = get_market_context()
    collection, is_vector_active = init_rag()
    
    context_chunks = []
    
    if is_vector_active and collection:
        try:
            # Search for top 3 relevant chunks via vector
            results = collection.query(
                query_texts=[question],
                n_results=3
            )
            context_chunks = results['documents'][0]
        except Exception:
            context_chunks = manual_retrieval(question, chunks)
    else:
        context_chunks = manual_retrieval(question, chunks)
    
    context = "\n---\n".join(context_chunks)
    
    client = Groq(api_key=GROQ_API_KEY)
    
    # Use the requested model with a fallback if it doesn't exist
    model_name = "meta-llama/llama-4-scout-17b-16e-instruct"
    
    try:
        completion = client.chat.completions.create(
            model=model_name,
            messages=[
                {
                    "role": "system",
                    "content": f"You are a Textile Market Expert. Provide a direct, data-rich answer based on the context below. \n\nFORMATTING RULES:\n- DO NOT USE ASTERISKS (**) for bolding. Use ALL CAPS for headers instead.\n- Use a clean vertical list (one item per line).\n- Use double newlines between main points for scannability.\n- Omit all introductory fluff and concluding notes.\n- If comparing prices, use a vertical list format.\n\nCONTEXT:\n{context}"
                },
                {
                    "role": "user",
                    "content": question
                }
            ],
            temperature=0.5,
            max_tokens=400,
            top_p=1,
            stream=False # Non-streaming for CLI output
        )
        return completion.choices[0].message.content
    except Exception as e:
        # Fallback to a guaranteed working model if the requested one is unavailable
        if "404" in str(e) or "not found" in str(e).lower():
            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {
                        "role": "system",
                        "content": f"You are a Textile Market Expert. Provide a direct, data-rich answer based on the context below. \n\nFORMATTING RULES:\n- DO NOT USE ASTERISKS (**) for bolding. Use ALL CAPS for headers instead.\n- Use a clean vertical list (one item per line).\n- Use double newlines between main points for scannability.\n- Omit all introductory fluff and concluding notes.\n\nCONTEXT:\n{context}"
                    },
                    {
                        "role": "user",
                        "content": question
                    }
                ],
                temperature=0.5,
                max_tokens=400
            )
            return completion.choices[0].message.content
        return f"Error: {str(e)}"

if __name__ == "__main__":
    query = ""
    
    # 1. Check stdin (preferred for runPythonCli)
    if not sys.stdin.isatty():
        try:
            raw_input = sys.stdin.read().strip()
            if raw_input:
                payload = json.loads(raw_input)
                # payload could be [question] or {"question": "..."}
                if isinstance(payload, list) and len(payload) > 0:
                    query = payload[0]
                elif isinstance(payload, dict):
                    query = payload.get("question") or payload.get("feedback") or ""
        except:
            pass

    # 2. Fallback to sys.argv
    if not query and len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])

    if query:
        ans = query_market(query)
        print(json.dumps({"response": ans}))
    else:
        print(json.dumps({"error": "No question provided"}))
