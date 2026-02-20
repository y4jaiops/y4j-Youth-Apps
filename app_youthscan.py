import streamlit as st
import pandas as pd
import time
from logic.style_manager import set_app_theme
from logic.auth_user import login_required
from logic.logic_drive import get_file_from_link
from logic.logic_gemini import parse_document_dynamic
from logic.logic_sheets import get_or_create_spreadsheet, append_batch_to_sheet

# 1. SETUP
set_app_theme("scan")
user = login_required()

st.write(f"Hi **{user['name']}**! Ready to scan candidates?")

# --- SESSION STATE INITIALIZATION ---
if "scanned_df" not in st.session_state:
    st.session_state["scanned_df"] = None
if "active_file" not in st.session_state:
    st.session_state["active_file"] = {"data": None, "mime": None}
if "uploader_key" not in st.session_state:
    st.session_state["uploader_key"] = 0

# 2. HELPER: RESET STATE
def full_reset():
    """Clears everything including the file uploader widget"""
    st.session_state["scanned_df"] = None
    st.session_state["active_file"] = {"data": None, "mime": None}
    st.session_state["uploader_key"] += 1 

def handle_mode_change():
    """Clears current files if the user switches input modes."""
    st.session_state["scanned_df"] = None
    st.session_state["active_file"] = {"data": None, "mime": None}

# 3. LAYOUT & NAVIGATION
col_nav, col_content = st.columns([1, 2])

with col_nav:
    # Highly accessible Radio group for navigation
    input_mode = st.radio(
        "Select Document Source:",
        ["Browse from Device", "Download from Google Drive", "Take Photo from Camera"],
        on_change=handle_mode_change
    )

# 4. INPUT LOGIC
with col_content:
    st.subheader(f"Mode: {input_mode}")

    if input_mode == "Browse from Device":
        up = st.file_uploader(
            "Select file to upload", 
            type=["jpg", "png", "jpeg", "pdf"], 
            key=f"u_widget_{st.session_state['uploader_key']}" 
        )
        if up: st.session_state["active_file"] = {"data": up.getvalue(), "mime": up.type}

    elif input_mode == "Take Photo from Camera":
        cam = st.camera_input("Take Photo")
        if cam: st.session_state["active_file"] = {"data": cam.getvalue(), "mime": "image/jpeg"}

    elif input_mode == "Download from Google Drive":
        st.info("Paste a link below to a file (not a folder) from Google Drive.")
        link = st.text_input("Google Drive Link:")
        if link and st.button("Fetch from Drive"):
            data, mime, err = get_file_from_link(link)
            if err: 
                st.error(err)
            else:
                st.success("✅ File Loaded Successfully!")
                st.session_state["active_file"] = {"data": data, "mime": mime}

# 5. PROCESSING
active_file = st.session_state["active_file"]

if active_file["data"] is not None:
    st.divider()
    if "image" in active_file["mime"]:
        st.image(active_file["data"], width=300)
    else:
        st.markdown(f"**Document Loaded: {active_file['mime']}**")
    
    default_cols = "First Name, Last Name, ID Type, ID Number, Email, Phone Number, Date Of Birth, Gender, Disability Type, Qualification, State"

    cols = st.text_area("Fields to Extract (comma separated)", value=default_cols).split(",")
    
    if st.button("Analyze Document", type="primary"):
        with st.spinner("Reading document..."):
            result = parse_document_dynamic(active_file["data"], cols, active_file["mime"], prompt_context="Youth Candidate Resume/ID")
            if "error" in result[0]: 
                st.error(result[0]["error"])
            else: 
                st.session_state["scanned_df"] = pd.DataFrame(result)

# 6. VERIFY & SAVE SECTION (OPTION 1: Static Table + Edit Form)
if st.session_state["scanned_df"] is not
