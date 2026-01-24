# (The AI Brain) Handles extraction for BOTH YouthScan and YouthJobs.
import streamlit as st
import google.generativeai as genai
import json
import pandas as pd

def configure_gemini():
    if "gemini" in st.secrets:
        genai.configure(api_key=st.secrets["gemini"]["api_key"])
        return True
    return False

def parse_document_dynamic(file_bytes, target_columns, mime_type, prompt_context="Candidate Data"):
    """
    Generic parser for Candidates or Jobs.
    Enforces English translation for Indic scripts.
    """
    if not configure_gemini():
        return [{"error": "Gemini API Key missing"}]

    model = genai.GenerativeModel('gemini-1.5-flash')
    
    # --- 📝 UPDATED PROMPT WITH TRANSLATION RULES ---
    prompt = f"""
    You are an expert data entry assistant for the Youth4Jobs Foundation.
    
    CONTEXT: 
    {prompt_context}
    
    TASK:
    Extract the following fields from the document: {', '.join(target_columns)}
    
    CRITICAL RULES:
    1. Output strictly valid JSON list of objects.
    2. If a field is missing, use "N/A".
    3. 🌐 TRANSLATION REQUIRED: If any text is in an Indic language (Hindi, Marathi, Telugu, Tamil, etc.) or Devanagari script, you MUST translate or transliterate it into English.
       - Example: If name is "रोहित शर्मा", output "Rohit Sharma".
       - Example: If education is "दसवीं पास", output "10th Pass".
    4. Do not include markdown formatting (like ```json) in your response. Just the raw JSON.
    """
    
    try:
        parts = [prompt, {"mime_type": mime_type, "data": file_bytes}]
        response = model.generate_content(parts)
        
        # Clean up response if the model ignores Rule #4
        json_text = response.text.replace("```json", "").replace("```", "").strip()
        
        data = json.loads(json_text)
        return data if isinstance(data, list) else [data]
        
    except Exception as e:
        return [{"error": f"AI Parsing Error: {str(e)}"}]
