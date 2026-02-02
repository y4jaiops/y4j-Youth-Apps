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
set_app_theme("jobs") # 🟢 Green Vibe
user = login_required()
genai.configure(api_key=st.secrets["gemini"]["api_key"])

st.title("🟢 YouthJobs: Input Portal")
st.write(f"Logged in as: **{user['name']}**")

# 2. INPUT SECTION
st.subheader("1. Upload Job Description")
input_method = st.radio("Source:", ["Paste Text", "Upload Image/PDF", "Camera"], horizontal=True)

extracted_text = ""
uploaded_file = None

if input_method == "Paste Text":
    extracted_text = st.text_area("Paste JD content here:", height=200)

elif input_method == "Upload Image/PDF":
    uploaded_file = st.file_uploader("Choose file", type=['png', 'jpg', 'jpeg', 'pdf'])

elif input_method == "Camera":
    uploaded_file = st.camera_input("Take a photo of the Job Poster")

# 3. AI EXTRACTION LOGIC
if st.button("🚀 Analyze Jobs", type="primary"):
    if not extracted_text and not uploaded_file:
        st.error("Please provide some input first!")
        st.stop()

    with st.spinner(f"Gemini ({GEMINI_MODEL_NAME}) is finding all jobs in this document..."):
        try:
            model = genai.GenerativeModel(GEMINI_MODEL_NAME)
            
            # A. PREPARE PROMPT
            base_prompt = """
            You are an expert HR Data Assistant.
            Analyze the provided Job Description (JD) content.
            
            CRITICAL INSTRUCTION:
            This single document might contain MULTIPLE distinct job roles (e.g., "We are hiring: 1. Sales Manager, 2. Driver").
            You must extract EACH job role as a separate object.
            
            Extract the following fields for EACH job:
            - Job Title
            - Company Name
            - Location
            - Min Experience (e.g., "0-1 Years")
            - Salary Range (e.g., "15k-20k")
            - Required Skills (comma separated)
            - Contact Email (if found)
            
            Output strictly a JSON LIST of objects:
            [
              {"Job Title": "...", "Company Name": "...", ...},
              {"Job Title": "...", "Company Name": "...", ...}
            ]
            """

            # B. SEND TO GEMINI
            response = None
            if uploaded_file:
                # Image/PDF processing
                import PIL.Image
                import fitz # PyMuPDF for PDF
                
                if uploaded_file.type == "application/pdf":
                    # Simple PDF text extraction for speed
                    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
