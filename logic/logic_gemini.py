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
    Generic parser for Candidates (YouthScan) or Jobs (YouthJobs).
    prompt_context: e.g., "Extract details for a Job Description" or "Extract details for a Candidate"
    """
    if not configure_gemini():
        return [{"error": "Gemini API Key missing"}]

    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = f"""
    You are an expert data entry assistant.
    Context: {prompt_context}
    
    Extract the following fields from the document: {', '.join(target_columns)}
    
    Output strictly valid JSON list of objects.
    If a field is missing, use "N/A".
    """
    
    try:
        parts = [prompt, {"mime_type": mime_type, "data": file_bytes}]
        response = model.generate_content(parts)
        
        json_text = response.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(json_text)
        return data if isinstance(data, list) else [data]
        
    except Exception as e:
        return [{"error": str(e)}]
