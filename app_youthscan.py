# app_youthscan.py (The Orange App 🟠)
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

st.write(f"👋 Hi **{user['name']}**! Ready to scan candidates?")

# --- SESSION STATE INITIALIZATION ---
if "scanned_df" not in st.session_state:
    st.session_state["scanned_df"] = None
if "input_mode" not in st.session_state:
    st.session_state["input_mode"] = "upload"
if "active_file" not in st.session_state:
    st.session_state["active_file"] = {"data": None, "mime": None}
# NEW: Key to force-clear the uploader widget
if "uploader_key" not in st.session_state:
    st.session_state["uploader_key"] = 0

# 2. HELPER: RESET STATE
def switch_mode(new_mode):
    st.session_state["input_mode"] = new_mode
    st.session_state["active_file"] = {"data": None, "mime": None}
    st.session_state["scanned_df"] = None
    # Don't increment uploader key here, only on save/clear
    
def full_reset():
    """Clears everything including the file uploader widget"""
    st.session_state["scanned_df"] = None
    st.session_state["active_file"] = {"data": None, "mime": None}
    st.session_state["uploader_key"] += 1 # <--- This wipes the uploader
    
# 3. LAYOUT
col_nav, col_content = st.columns([1, 3])

with col_nav:
    st.info("Select Source for Document to scan:")
    if st.button("📂 Scan Photo/PDF stored on phone/computer", use_container_width=True):
        switch_mode("Browse from phone/computer")
    if st.button("🔗 Scan Photo/PDF from Google Drive", use_container_width=True):
        switch_mode("Download from Google drive")
    if st.button("📸 Scan with new photo from Camera", use_container_width=True):
        switch_mode("Take photo from camera")

# 4. INPUT LOGIC
with col_content:
    mode = st.session_state["input_mode"]
    st.subheader(f"Mode: {mode.title()}")

    if mode == "upload":
        # We use the dynamic key here. When it changes, this widget is destroyed and recreated empty.
        up = st.file_uploader(
            "Select file", 
            type=["jpg", "png", "jpeg", "pdf"], 
            key=f"u_widget_{st.session_state['uploader_key']}" 
        )
        if up: st.session_state["active_file"] = {"data": up.getvalue(), "mime": up.type}

    elif mode == "camera":
        cam = st.camera_input("Take Photo")
        if cam: st.session_state["active_file"] = {"data": cam.getvalue(), "mime": "image/jpeg"}

    elif mode == "drive":
        st.info("Paste a link below to a file (not a folder) from Google Drive.")
        link = st.text_input("Google Drive Link below this line:")
        if link and st.button("Fetch from Drive"):
            data, mime, err = get_file_from_link(link)
            if err: st.error(err)
            else:
                st.success("✅ File Loaded!")
                st.session_state["active_file"] = {"data": data, "mime": mime}

# 5. PROCESSING
active_file = st.session_state["active_file"]

if active_file["data"] is not None:
    st.divider()
    if "image" in active_file["mime"]:
        st.image(active_file["data"], width=300)
    else:
        st.markdown(f"**📄 Document Loaded: {active_file['mime']}**")
    
    default_cols = "First Name,	Last Name,	ID Type,	ID Number,	Email,	Phone Number,	Date Of Birth,	Gender,	Disability Type,	Qualification,	State"

    cols = st.text_area("Fields to Extract", value=default_cols).split(",")
    
    if st.button("🚀 Analyze with Gemini", type="primary"):
        with st.spinner("Gemini is reading..."):
            result = parse_document_dynamic(active_file["data"], cols, active_file["mime"], prompt_context="Youth Candidate Resume/ID")
            if "error" in result[0]: st.error(result[0]["error"])
            else: st.session_state["scanned_df"] = pd.DataFrame(result)

# 6. SAVE SECTION
if st.session_state["scanned_df"] is not None:
    st.divider()
    st.subheader("Verify & Save")
    
    edited_df = st.data_editor(st.session_state["scanned_df"], num_rows="dynamic")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        sheet_name = st.text_input("Target Sheet", value="YouthScan_Data")
    with col2:
        st.write("")
        st.write("")
        if st.button("💾 Save to Cloud"):
            with st.spinner("Saving..."):
                fid = st.secrets.get("youthscan", {}).get("folder_id")
                url = get_or_create_spreadsheet(sheet_name, fid)
                if url and append_batch_to_sheet(url, edited_df.to_dict('records')):
                    st.success("✅ Saved successfully!")
                    st.balloons()
                    
                    # --- 🧹 THE CLEANUP LOGIC ---
                    time.sleep(2) 
                    full_reset() # This now rotates the key
                    st.rerun()
