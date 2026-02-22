import google.generativeai as genai
import json
import streamlit as st

# --- 🎯 CENTRAL CONFIGURATION (The Single Source of Truth) ---
# Change this ONE line to upgrade the "Brain" for ALL apps.
# Options: 'gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-2.0-flash-exp'
GEMINI_MODEL_NAME = "gemini-3-flash-preview"

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
    Generic function to extract specific fields from ANY image/PDF/Text.
    Uses the Central Model Configuration.
    """
    model = get_gemini_model()
    if not model:
        return [{"error": "Model initialization failed"}]

    # 1. Construct the Prompt dynamically based on requested fields
    # Strip whitespace from fields to ensure clean keys
    fields_str = ", ".join([f'"{f.strip()}"' for f in fields_list])
    
    prompt = f"""
    Context: Analyze this {prompt_context}. The provided data may contain ONE or MORE distinct candidate profiles or resumes.
    
    Task:
    1. Identify every individual candidate in the text, image, or document.
    2. For EACH candidate, extract the following specific information: {fields_str}.
    3. If a field is not found for a candidate, return "N/A" for that field. Do not skip the key.
    
    Output Format:
    You MUST output the result strictly as a valid JSON array of objects.
    Example format: [{{"Field 1": "Value", "Field 2": "N/A"}}, {{"Field 1": "Value 2", "Field 2": "Value"}}]
    """

    # 2. Prepare the data payload based on mime type
    if mime_type == "text/plain":
        # For pasted text, decode bytes to string and pass directly
        document_part = file_bytes.decode("utf-8")
    else:
        # For images and PDFs, pass the dictionary format expected by Gemini
        document_part = {
            "mime_type": mime_type,
            "data": file_bytes
        }

    # 3. Call Gemini with strict JSON configuration
    try:
        response = model.generate_content(
            [prompt, document_part],
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.1 # Low temperature for reliable factual extraction
            )
        )
        
        # 4. Clean and Parse JSON
        text_response = response.text
        # Markdown stripping acts as a safe fallback even with JSON mode enabled
        clean_json = text_response.replace("```json", "").replace("```", "").strip()
        
        extracted_data = json.loads(clean_json)
        
        # Ensure the output is ALWAYS a list, even if only one record was found
        if isinstance(extracted_data, dict):
            return [extracted_data]
            
        return extracted_data

    except Exception as e:
        return [{"error": f"AI Parsing Error: {str(e)}"}]
