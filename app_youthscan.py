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
    st.session_state["input_mode"] = "upload"
# NEW: Persistent storage for the file itself
if "active_file" not in st.session_state:
    st.session_state["active_file"] = {"data": None, "mime": None}

# 2. HELPER: RESET STATE
def switch_mode(new_mode):
    st.session_state["input_mode"] = new_mode
    # Clear previous file when switching modes
    st.session_state["active_file"] = {"data": None, "mime": None}
    st.session_state["scanned_df"] = None

# 3. LAYOUT
col_nav, col_content = st.columns([1, 3])

with col_nav:
    st.info("Select Source:")
    if st.button("📂 Upload Phone/PDF", use_container_width=True):
        switch_mode("upload")
    
    if st.button("🔗 Google Drive", use_container_width=True):
        switch_mode("drive")
        
    if st.button("📸 Camera", use_container_width=True):
        switch_mode("camera")

# 4. INPUT LOGIC
with col_content:
    mode = st.session_state["input_mode"]
    st.subheader(f"Mode: {mode.title()}")

    # --- MODE 1: UPLOAD ---
    if mode == "upload":
        up = st.file_uploader("Select file", type=["jpg", "png", "jpeg", "pdf"], key="u_widget")
        if up:
            st.session_state["active_file"] = {"data": up.getvalue(), "mime": up.type}

    # --- MODE 2: CAMERA ---
    elif mode == "camera":
        cam = st.camera_input("Take Photo")
        if cam:
            st.session_state["active_file"] = {"data": cam.getvalue(), "mime": "image/jpeg"}

    # --- MODE 3: DRIVE (The tricky one) ---
    elif mode == "drive":
        st.info("Paste a link to a file (not a folder) from Google Drive.")
        link = st.text_input("Google Drive Link")
        if link and st.button("Fetch from Drive"):
            data, mime, err = get_file_from_link(link)
            if err:
                st.error(err)
            else:
                st.success("✅ File Loaded! You can now analyze it.")
                # SAVE TO STATE immediately
                st.session_state["active_file"] = {"data": data, "mime": mime}

# 5. PROCESSING (Uses the persistent state)
active_file = st.session_state["active_file"]

if active_file["data"] is not None:
    st.divider()
    
    # Preview
    if "image" in active_file["mime"]:
        st.image(active_file["data"], width=300)
    else:
        st.markdown(f"**📄 Document Loaded: {active_file['mime']}**")
    
    default_cols = "First Name, Last Name, Email, Phone, Disability Type, Education, State"
    cols = st.text_area("Fields to Extract", value=default_cols).split(",")
    
    # --- THE ANALYZE BUTTON ---
    if st.button("🚀 Analyze with Gemini", type="primary"):
        with st.spinner("Gemini is reading the document..."):
            result = parse_document_dynamic(
                active_file["data"], 
                cols, 
                active_file["mime"], 
                prompt_context="Youth Candidate Resume/ID"
            )
            
            if "error" in result[0]:
                st.error(result[0]["error"])
            else:
                st.session_state["scanned_df"] = pd.DataFrame(result)

# 6. SAVE SECTION (Outside the Analyze loop)
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
                    st.success("✅ Saved!")
                    st.balloons()
