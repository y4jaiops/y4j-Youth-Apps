import streamlit as st
import pandas as pd
import json
import time
import google.generativeai as genai
from logic.style_manager import set_app_theme
from logic.auth_user import login_required
from logic.logic_sheets import get_or_create_spreadsheet, append_batch_to_sheet
from logic.logic_gemini import GEMINI_MODEL_NAME

# 1. SETUP
set_app_theme("scan") # 🟠 Orange Vibe
user = login_required()
genai.configure(api_key=st.secrets["gemini"]["api_key"])

st.title("🟠 YouthScan: Candidate Entry")
st.write(f"Logged in as: **{user['name']}**")

# 2. INPUT SECTION
st.subheader("1. Input Candidate Data")
input_method = st.radio("Source:", ["Paste Text", "Upload Resume/ID", "Camera"], horizontal=True)

extracted_text = ""
uploaded_file = None

if input_method == "Paste Text":
    # --- FIX IS HERE: help="..." instead of help(...) ---
    extracted_text = st.text_area(
        "Paste Resume/Bio-data content here:", 
        height=200, 
        help="Paste text from WhatsApp, Email, or Word doc."
    )

elif input_method == "Upload Resume/ID":
    uploaded_file = st.file_uploader("Choose file", type=['png', 'jpg', 'jpeg', 'pdf'])

elif input_method == "Camera":
    uploaded_file = st.camera_input("Take a photo of Resume/ID Card")

# 3. AI EXTRACTION LOGIC
if st.button("🚀 Scan Candidate", type="primary"):
    # Check if we have ANY input
    if not extracted_text and not uploaded_file:
        st.error("Please provide some input (Text or File) first!")
        st.stop()

    with st.spinner(f"Gemini ({GEMINI_MODEL_NAME}) is reading the profile..."):
        try:
            model = genai.GenerativeModel(GEMINI_MODEL_NAME)
            
            # A. PREPARE PROMPT
            base_prompt = """
            You are an expert Data Entry Clerk for a Disability NGO.
            Extract candidate details from the provided input.
            
            Extract these exact fields:
            - First Name
            - Last Name
            - Phone Number
            - Email
            - State (Location)
            - Disability Type (e.g., Locomotor, Visual, Hearing, Speech)
            - Education (Highest Qualification)
            - Skills (Comma separated)
            
            Output strictly a JSON object:
            {"First Name": "...", "Last Name": "...", ...}
            """

            # B. SEND TO GEMINI
            response = None
            
            if input_method == "Paste Text":
                # Text Input Logic
                response = model.generate_content([base_prompt, extracted_text])
                
            elif uploaded_file:
                # File/Camera Logic
                import PIL.Image
                import fitz # PyMuPDF for PDF
                
                if uploaded_file.type == "application/pdf":
                    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
                    pdf_text = ""
                    for page in doc:
                        pdf_text += page.get_text()
                    response = model.generate_content([base_prompt, pdf_text])
                else:
                    img = PIL.Image.open(uploaded_file)
                    response = model.generate_content([base_prompt, img])

            # C. PARSE JSON
            cleaned_json = response.text.replace("```json", "").replace("```", "").strip()
            data_dict = json.loads(cleaned_json)
            
            # Save to session state for review
            st.session_state['scanned_candidate'] = data_dict
            st.rerun()

        except Exception as e:
            st.error(f"AI Error: {e}")

# 4. REVIEW & SAVE SECTION
if 'scanned_candidate' in st.session_state:
    st.divider()
    st.subheader("2. Verify & Save")
    
    # We use a Form so the user can edit mistakes before saving
    with st.form("verify_form"):
        c_data = st.session_state['scanned_candidate']
        
        col1, col2 = st.columns(2)
        with col1:
            f_name = st.text_input("First Name", c_data.get("First Name", ""))
            phone = st.text_input("Phone", c_data.get("Phone Number", ""))
            state = st.text_input("State", c_data.get("State", ""))
            disability = st.text_input("Disability Type", c_data.get("Disability Type", ""))
        
        with col2:
            l_name = st.text_input("Last Name", c_data.get("Last Name", ""))
            email = st.text_input("Email", c_data.get("Email", ""))
            edu = st.text_input("Education", c_data.get("Education", ""))
            skills = st.text_input("Skills", c_data.get("Skills", ""))

        submitted = st.form_submit_button("✅ Save to Database", type="primary")
        
        if submitted:
            # Re-package the edited data
            final_data = {
                "First Name": f_name,
                "Last Name": l_name,
                "Phone Number": phone,
                "Email": email,
                "State": state,
                "Disability Type": disability,
                "Education": edu,
                "Skills": skills,
                "Added By": user['name'],
                "Date Added": time.strftime("%Y-%m-%d")
            }
            
            # Load Database URL
            fid = st.secrets.get("youthscan", {}).get("folder_id")
