# app_youthscan.py (The Orange App 🟠)

import streamlit as st
import pandas as pd
from logic.style_manager import set_app_theme
from logic.auth_user import login_required
from logic.logic_drive import get_file_from_link
from logic.logic_gemini import parse_document_dynamic
from logic.logic_sheets import get_or_create_spreadsheet, append_batch_to_sheet

# 1. SETUP
set_app_theme("scan")
user = login_required()

st.write(f"👋 Hi **{user['name']}**! Ready to scan candidates?")

# --- SESSION STATE INITIALIZATION ---
if "scanned_df" not in st.session_state:
    st.session_state["scanned_df"] = None

# 2. INPUTS
tab1, tab2 = st.tabs(["📸 Camera / Upload", "🔗 Drive Link"])
file_bytes = None
mime = "image/jpeg"

with tab1:
    cam = st.camera_input("Take Photo")
    up = st.file_uploader("Or Upload File", type=["jpg","png","pdf"])
    if cam: file_bytes = cam.getvalue()
    elif up: 
        file_bytes = up.getvalue()
        mime = up.type

with tab2:
    link = st.text_input("Paste Google Drive Link")
    if link and st.button("Fetch"):
        file_bytes, mime, err = get_file_from_link(link)
        if err: st.error(err)
        else: st.success("Loaded!")

# 3. PROCESSING
if file_bytes:
    default_cols = "First Name, Last Name, Email, Phone, Disability Type, Education, State"
    cols = st.text_area("Fields to Extract", value=default_cols).split(",")
    
    # ACTION: SCAN
    if st.button("🚀 Scan Document"):
        with st.spinner("AI is reading..."):
            data = parse_document_dynamic(file_bytes, cols, mime, prompt_context="Youth Candidate Resume/ID")
            
            if "error" in data[0]:
                st.error(data[0]["error"])
            else:
                # SAVE TO SESSION STATE (Persist the data!)
                st.session_state["scanned_df"] = pd.DataFrame(data)

# 4. REVIEW & SAVE (Outside the Scan Button)
if st.session_state["scanned_df"] is not None:
    st.divider()
    st.subheader("Verify Data")
    
    # Allow editing the persistent data
    edited_df = st.data_editor(
        st.session_state["scanned_df"], 
        num_rows="dynamic", 
        key="editor"
    )
    
    target_sheet = st.text_input("Sheet Name", value="YouthScan_Data")
    
    # ACTION: SAVE
    if st.button("💾 Save to Cloud"):
        with st.spinner("Saving to Google Drive..."):
            folder_id = st.secrets.get("youthscan", {}).get("folder_id")
            
            # 1. Get/Create Sheet
            url = get_or_create_spreadsheet(target_sheet, folder_id)
            
            if url:
                # 2. Append Data
                data_to_save = edited_df.to_dict('records')
                if append_batch_to_sheet(url, data_to_save):
                    st.success("✅ Saved successfully!")
                    st.balloons()
                    # Optional: Clear data after save
                    # st.session_state["scanned_df"] = None 
                    # st.rerun()
            else:
                st.error("Failed to create spreadsheet. Check permissions.")
