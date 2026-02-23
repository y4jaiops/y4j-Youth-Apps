import streamlit as st
import pandas as pd
import json
import time
import base64
import google.generativeai as genai
import PIL.Image
try:
    import fitz 
except ImportError:
    st.warning("⚠️ PyMuPDF (fitz) is missing. Please add 'pymupdf' to requirements.txt")

from logic.style_manager import set_app_theme
from logic.auth_user import login_required
from logic.logic_sheets import get_or_create_spreadsheet, append_batch_to_sheet
from logic.logic_gemini import GEMINI_MODEL_NAME

# 1. SETUP
set_app_theme("jobscan") 
user = login_required()
genai.configure(api_key=st.secrets["gemini"]["api_key"])

st.title("🟢 Jobscan: Jobs Input App")
st.write(f"Logged in as: **{user['name']}**")

# Helper Function for Visual and Audio Feedback
def trigger_success_feedback():
    """Triggers the balloons animation and plays an invisible success chime reliably."""
    st.balloons()
    try:
        with open("koiroylers-awesome-notification-351720.mp3", "rb") as f:
            data = f.read()
            b64 = base64.b64encode(data).decode()
        
        unique_id = str(time.time()).replace('.', '')
        md = f"""
            <audio id="{unique_id}" autoplay="true" style="display:none;">
            <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
            </audio>
            """
        st.markdown(md, unsafe_allow_html=True)
    except Exception:
        pass
 
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

if uploaded_file:
    st.divider()
    st.caption("📄 Document Preview:")
    
    if uploaded_file.type in ["image/png", "image/jpeg", "image/jpg"]:
        st.image(uploaded_file, width=300, caption="Ready to Analyze")
    
    elif uploaded_file.type == "application/pdf":
        st.success(f"📂 PDF Loaded: {uploaded_file.name}")

# 3. AI EXTRACTION LOGIC
if st.button("🚀 Analyze Jobs", type="primary"):
    if not extracted_text and not uploaded_file:
        st.error("Please provide some input first!")
        st.stop()

    with st.spinner(f"Gemini ({GEMINI_MODEL_NAME}) is finding all jobs in this document..."):
        try:
            model = genai.GenerativeModel(GEMINI_MODEL_NAME)
            
            base_prompt = """
            You are an expert HR Data Assistant.
            Analyze the provided Job Description (JD) content.
            
            CRITICAL INSTRUCTION:
            This single document might contain MULTIPLE distinct job roles (e.g., "We are hiring: 1. Sales Manager, 2. Driver").
            You must extract EACH job role as a separate object.
            When there are multiple locations listed, extract information per location, and treat them as distict job opening.
            
            Extract the following fields for EACH job:
            - Job Title
            - Company Name
            - Location
            - Min Experience (e.g., "0-1 Years")
            - Salary Range (e.g., "15k-20k")
            - Required Skills (comma separated)
            - Contact Email (if found)
            - Contact phone (if found)
            - Website Link (if found)
            - Last date to apply (if found)
            - PWD (if found)
            - Application Fee (if found)
            
            Output strictly a JSON LIST of objects:
            [
              {"Job Title": "...", "Company Name": "...", ...},
              {"Job Title": "...", "Company Name": "...", ...}
            ]
            """

            response = None
            if uploaded_file:
                if uploaded_file.type == "application/pdf":
                    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
                    pdf_text = ""
                    for page in doc:
                        pdf_text += page.get_text()
                    response = model.generate_content([base_prompt, pdf_text])
                else:
                    img = PIL.Image.open(uploaded_file)
                    response = model.generate_content([base_prompt, img])
            else:
                response = model.generate_content([base_prompt, extracted_text])

            cleaned_json = response.text.replace("```json", "").replace("```", "").strip()
            data_list = json.loads(cleaned_json)
            
            if isinstance(data_list, dict):
                data_list = [data_list]
                
            st.session_state['extracted_jobs'] = data_list
            st.rerun()

        except Exception as e:
            st.error(f"AI Error: {e}")

# 4. REVIEW & SAVE SECTION
if 'extracted_jobs' in st.session_state:
    st.divider()
    st.subheader("2. Review & Save")
    st.info(f"✅ Found {len(st.session_state['extracted_jobs'])} distinct roles.")

    df_preview = pd.DataFrame(st.session_state['extracted_jobs'])
    
    required_cols = ["Job Title", "Company Name", "Location", "Salary Range", "Required Skills", "Contact Email"]
    for col in required_cols:
        if col not in df_preview.columns:
            df_preview[col] = ""

    df_preview = df_preview[required_cols + [c for c in df_preview.columns if c not in required_cols]]

    edited_df = st.data_editor(
        df_preview,
        num_rows="dynamic",
        use_container_width=True,
        key="job_editor"
    )

    st.divider()
    st.markdown("**Finalize & Save:**")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        volunteer_email = user.get("email", "volunteer")
        default_sheet_name = f"JobScan_{volunteer_email}"
        sheet_name = st.text_input("Google Sheet Name (Saving Destination)", value=default_sheet_name)
    
    with col2:
        st.write("") 
        st.write("") 
        final_save = st.button("💾 Save All Jobs", type="primary", use_container_width=True)

# --- SAVE LOGIC ---
    if final_save:
        with st.spinner("Syncing to Google Sheets..."):
            fid = st.secrets.get("jobscan", {}).get("folder_id")
            
            if not fid:
                st.error("❌ Folder ID missing! Check that your secrets.toml has a [jobscan] section with the folder_id.")
                st.stop()

            url = get_or_create_spreadsheet(sheet_name, fid)
            
            if url:
                final_data = edited_df.to_dict(orient='records')
                
                for row in final_data:
                    row['Added By'] = user['name']
                    row['Date Added'] = time.strftime("%Y-%m-%d")
                
                if append_batch_to_sheet(url, final_data):
                    st.toast(f"🎉 Saved {len(final_data)} jobs!", icon="✅")
                    trigger_success_feedback()
                    del st.session_state['extracted_jobs']
                    time.sleep(2.5)
                    st.rerun()
                else:
                    st.error("❌ Save failed. Check logs.")
