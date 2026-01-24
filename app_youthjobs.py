# app_youthjobs.py (The Green App 🟢) YouthJobs

import streamlit as st
import pandas as pd
from logic.style_manager import set_app_theme
from logic.auth_user import login_required
from logic.logic_gemini import parse_document_dynamic
from logic.logic_sheets import get_or_create_spreadsheet, append_batch_to_sheet

# 1. SETUP
set_app_theme("jobs") # 🟢 Green Vibe
user = login_required()

st.write(f"👋 Hi **{user['name']}**! Let's digitize some Job Descriptions.")

# 2. INPUTS ( simplified for Jobs)
up = st.file_uploader("Upload Job Description (PDF/Image)", type=["pdf", "png", "jpg"])

# 3. PROCESSING
if up:
    # Different Columns for Jobs
    default_cols = "Job Title, Company Name, Location, Salary Range, Required Skills, Min Experience, Contact Email"
    cols = st.text_area("Fields to Extract", value=default_cols).split(",")
    
    if st.button("🚀 Digitize Job"):
        with st.spinner("AI is analyzing requirements..."):
            # Context changed to "Job Description"
            data = parse_document_dynamic(up.getvalue(), cols, up.type, prompt_context="Job Description Document")
            
            if "error" in data[0]:
                st.error(data[0]["error"])
            else:
                df = pd.DataFrame(data)
                st.data_editor(df, num_rows="dynamic")
                
                if st.button("💾 Save to Jobs Database"):
                    folder_id = st.secrets.get("youthjobs", {}).get("folder_id")
                    url = get_or_create_spreadsheet("YouthJobs_Master_DB", folder_id)
                    if url and append_batch_to_sheet(url, df.to_dict('records')):
                        st.success("✅ Job Added to Database!")
