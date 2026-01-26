import google.generativeai as genai
import json
import streamlit as st

# --- 🎯 CENTRAL CONFIGURATION (The Single Source of Truth) ---
# Change this ONE line to upgrade the "Brain" for ALL apps.
# Options: 'gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-2.0-flash-exp'
GEMINI_MODEL_NAME = "gemini-1.5-flash"

def get_gemini_model():
    """
    Configures and returns a Gemini model instance using the central model name.
    """
    # 1. Configure the API Key safely
    if "gemini" in st.secrets and "api_key" in st.secrets["gemini"]:
        genai.configure(api_key=st.secrets["gemini"]["api_key"])
    else:
        st.error("❌ Gemini API Key missing in secrets.toml")
        return None

    # 2. Return the Model defined in the constant above
    return genai.GenerativeModel(GEMINI_MODEL_NAME)

def parse_document_dynamic(file_bytes, fields_list, mime_type, prompt_context="Document"):
    """
    Generic function to extract specific fields from ANY image/PDF.
    Uses the Central Model Configuration.
    """
    model = get_gemini_model()
    if not model:
        return [{"error": "Model initialization failed"}]

    # 1. Construct the Prompt dynamically based on requested fields
    fields_str = ", ".join(fields_list)
    
    prompt = f"""
    Analyze this {prompt_context}.
    Extract the following specific information: {fields_str}.
    
    Strictly output the result as a valid JSON list of dictionaries.
    Example format: [{{"Field Name": "Value"}}]
    If a field is not found, return "N/A" for that field.
    """

    # 2. Prepare the data part (Image or PDF)
    document_part = {
        "mime_type": mime_type,
        "data": file_bytes
    }

    # 3. Call Gemini
    try:
        response = model.generate_content([prompt, document_part])
        
        # 4. Clean and Parse JSON
        text_response = response.text
        # Remove markdown code blocks if present
        clean_json = text_response.replace("```json", "").replace("```", "").strip()
        
        return json.loads(clean_json)

    except Exception as e:
        return [{"error": f"AI Parsing Error: {str(e)}"}]
