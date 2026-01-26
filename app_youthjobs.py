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
        up = st.file_uploader(
            "Select JD file", 
            type=["pdf", "png", "jpg"], 
            key=f"jd_widget_{st
