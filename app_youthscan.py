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
if "input_mode" not in st.session_state:
    st.session_state["input_mode"] = "upload" # Default mode

# 2. LAYOUT: Left (Buttons) vs Right (Content)
col_nav, col_content = st.columns([1, 3])

with col_nav:
    st.info("Select Source:")
    # Vertical Buttons behaving like Tabs
    if st.button("📂 Upload Phone/PDF", use_container_width=True):
        st.session_state["input_mode"] = "upload"
    
    if st.button("🔗 Google Drive", use_container_width=True):
        st.session_state["input_mode"] = "drive"
        
    if st.button("📸 Camera", use_container_width=True):
        st.session_state["input_mode"] = "camera"

# 3. INPUT LOGIC (Based on Mode)
file_bytes = None
mime = "image/jpeg"

with col_content:
    current_mode = st.session_state["input_mode"]
    
    st.subheader(f"Mode: {current_mode.title()}")

    # --- MODE 1: PHONE UPLOAD ---
    if current_mode == "upload":
        up = st.file_uploader("Select file", type=["jpg", "png", "jpeg", "pdf"], key="file_upload_widget")
        if up:
            file_bytes = up.getvalue()
            mime = up.type

    # --- MODE 2: GOOGLE DRIVE ---
    elif current_mode == "drive":
        st.info("Paste a link to a file (not a folder) from Google Drive.")
        link = st.text_input("Google Drive Link")
        if link and st.button("Fetch from Drive"):
            file_bytes, mime, err = get_file_from_link(link)
            if err: 
                st.error(err)
                file_bytes = None
            else: 
                st.success("✅ File Loaded Successfully!")

    # --- MODE 3: CAMERA ---
    elif current_mode == "camera":
        cam = st.camera_input("Take Photo of ID/Resume")
        if cam:
            file_bytes = cam.getvalue()
            mime = "image/jpeg"

# 4. PROCESSING (
