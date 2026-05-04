import os
import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from contextlib import asynccontextmanager
from transformers import AutoTokenizer, AutoModelForCausalLM

# We will store the loaded model and tokenizer here so they persist
ml_models = {}

# ── 1. Load Model Once on Startup ───────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("⏳ Loading text model into memory... This might take a minute.")
    
    # Point this to the local folder where you downloaded the weights
    local_model_path = os.path.join(os.environ.get('WORKSPACE_ROOT', os.path.join(os.environ.get('WORKSPACE_ROOT', '.'), 'AgenticControl/local_qwen_model" )
    
    # Added trust_remote_code=True here as well
    tokenizer = AutoTokenizer.from_pretrained(
        local_model_path,
        trust_remote_code=True
    )
    
    model = AutoModelForCausalLM.from_pretrained(
        local_model_path, 
        device_map="auto", 
        torch_dtype="auto", # Saves memory by using the optimal precision
        trust_remote_code=True
    )
    
    ml_models["tokenizer"] = tokenizer
    ml_models["model"] = model
    
    print("✅ Model loaded successfully! Server is ready for text requests.")
    yield
    
    # Clean up when the server shuts down
    ml_models.clear()
    print("🛑 Server shutting down, memory cleared.")

# Initialize the FastAPI app with the lifespan manager
app = FastAPI(lifespan=lifespan)

# ── 2. Define the Request Data Structure ────────────────────────────────
class GenerateRequest(BaseModel):
    system_prompt: str
    query: str
    max_new_tokens: int = 200 # Increased default since text answers are usually longer

# ── 3. Create the API Endpoint ──────────────────────────────────────────
@app.post("/generate")
async def generate(request: GenerateRequest):
    try:
        tokenizer = ml_models["tokenizer"]
        model = ml_models["model"]
        
        # Format the prompt using the standard system/user role structure
        messages = [
            {"role": "system", "content": request.system_prompt},
            {"role": "user", "content": request.query}
        ]
        
        # Generate the formatted text string first (avoids dictionary/tensor errors)
        text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
        
        # Tokenize the formatted string into PyTorch tensors and send to GPU/CPU
        model_inputs = tokenizer([text], return_tensors="pt").to(model.device)

        # Generate response
        generated_ids = model.generate(
            **model_inputs, 
            max_new_tokens=request.max_new_tokens
        )
        
        # Decode only the newly generated text (ignoring the input prompt tokens)
        generated_ids = [
            output_ids[len(input_ids):] for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
        ]
        
        result_text = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]
        
        return {"response": result_text}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))