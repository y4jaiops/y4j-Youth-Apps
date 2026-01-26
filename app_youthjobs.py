# app_youthjobs.py (The Green App 🟢) YouthJobs
import streamlit as st
import pandas as pd
import time
from logic.style_manager import set_app_theme
from logic.auth_user import login_required
from logic.logic_drive import get_file_from_link
from logic.logic_gemini import parse_document_dynamic
from logic.logic_sheets import get_or_create_spreadsheet, append_batch_to_sheet

# 1. SETUP
set_app_theme("jobs") # 🟢 Green Vibe
user = login_required()

st.write(f"👋 Hi **{user['name']}**! Ready to digitize Job Descriptions?")

# --- SESSION STATE INITIALIZATION ---
if "job_df" not in st.session_state:
    st.session_state["job_df"] = None
if "input_mode" not in st.session_state:
    st.session_state["input_mode"] = "upload"
if "active_file" not in st.session_state:
    st.session_state["active_file"] = {"data": None, "mime": None}
if "uploader_key" not in st.session_state:
    st.session_state["uploader_key"] = 0

# 2. HELPER: RESET STATE
def switch_mode(new_mode):
    st.session_state["input_mode"] = new_mode
    st.session_state["active_file"] = {"data": None, "mime": None}
    st.session_state["job_df"] = None

def full_reset():
    st.session_state["job_df"] = None
    st.session_state["active_file"] = {"data": None, "mime": None}
    st.session_state["uploader_key"] += 1 

# 3. LAYOUT
col_nav, col_content = st.columns([1, 3])

with col_nav:
    st.info("Select Source:")
    if st.button("📂 Upload PDF/Image", use_container_width=True):
        switch_mode("upload")
    if st.button("🔗 Google Drive", use_container_width=True):
        switch_mode("drive")
    if st.button("📸 Camera", use_container_width=True):
        switch_mode("camera")

# 4. INPUT LOGIC
with col_content:
    mode = st.session_state["input_mode"]
    st.subheader(f"Mode: {mode.title()}")

    if mode == "upload":
        # Simplified key generation to prevent syntax errors
        ukey = st.session_state['uploader_key']
        up = st.file_uploader(
            "Select JD file", 
            type=["pdf", "png", "jpg"], 
            key=f"jd_widget_{ukey}"
        )
        if up: st.session_state["active_file"] = {"data": up.getvalue(), "mime": up.type}

    elif mode == "drive":
        st.info("Paste a link to a JD file from Google Drive.")
        link = st.text_input("Google Drive Link")
        if link and st.button("Fetch from Drive"):
            data, mime, err = get_file_from_link(link)
            if err: 
                st.error(err)
            else:
                st.success("✅ File Loaded!")
                st.session_state["active_file"] = {"data": data, "mime": mime}
                
    elif mode == "camera":
        cam = st.camera_input("Take Photo of JD")
        if cam: st.session_state["active_file"] = {"data": cam.getvalue(), "mime": "image/jpeg"}

# 5. PROCESSING
active_file = st.session_state["active_file"]

if active_file["data"] is not None:
    st.divider()
    if "image" in active_file["mime"]:
        st.image(active_file["data"], width=300)
    else:
        st.markdown(f"**📄 Document Loaded: {active_file['mime']}**")
    
    # --- JOB SPECIFIC FIELDS ---
    default_cols = "Job Title, Company Name, Location, Salary Range, Required Skills, Min Experience, Contact Email"
    cols = st.text_area("Fields to Extract", value=default_cols).split(",")
    
    if st.button("🚀 Analyze Job Description", type="primary"):
        with st.spinner("AI is analyzing requirements..."):
            result = parse_document_dynamic(
                active_file["data"], 
                cols, 
                active_file["mime"], 
                prompt_context="Job Description Document"
            )
            
            if "error" in result[0]: st.error(result[0]["error"])
            else: st.session_state["job_df"] = pd.DataFrame(result)

# 6. SAVE SECTION
if st.session_state["job_df"] is not None:
    st.divider()
    st.subheader("Verify & Save")
    
    edited_df = st.data_editor(st.session_state["job_df"], num_rows="dynamic")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        sheet_name = st.text_input("Target Sheet", value="YouthJobs_Master_DB")
    with col2:
        st.write("")
        st.write("")
        
        if st.button("💾 Save to Cloud"):
            with st.spinner("Saving..."):
                fid = st.secrets.get("youthjobs", {}).get("folder_id")
                url = get_or_create_spreadsheet(sheet_name, fid)
                
                if url and append_batch_to_sheet(url, edited_df.to_dict('records')):
                    st.success("✅ Saved successfully!")
                    st.balloons()
                    time.sleep(2) 
                    full_reset()
                    st.rerun()
                else:
                    st.error("❌ Save failed. Please check your internet connection or permissions.")
