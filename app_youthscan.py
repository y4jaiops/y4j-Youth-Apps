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

# 2. INPUTS (Reordered: Phone Upload -> Drive -> Camera)
tab_up, tab_link, tab_cam = st.tabs([
    "📂 Scan PDF/Photo from phone", 
    "🔗 Scan PDF/Photo from Google Drive", 
    "📸 Camera"
])

file_bytes = None
mime = "image/jpeg"

# --- TAB 1: PHONE UPLOAD ---
with tab_up:
    up = st.file_uploader("Select file", type=["jpg", "png", "jpeg", "pdf"], key="file_upload_widget")
    if up:
        file_bytes = up.getvalue()
        mime = up.type

# --- TAB 2: GOOGLE DRIVE ---
with tab_link:
    st.info("Paste a link to a file (not a folder) from Google Drive.")
    link = st.text_input("Google Drive Link")
    if link and st.button("Fetch from Drive"):
        file_bytes, mime, err = get_file_from_link(link)
        if err: 
            st.error(err)
            file_bytes = None # Reset on error
        else: 
            st.success("✅ File Loaded Successfully!")

# --- TAB 3: CAMERA ---
with tab_cam:
    cam = st.camera_input("Take Photo of ID/Resume")
    if cam:
        file_bytes = cam.getvalue()
        mime = "image/jpeg"

# 3. PROCESSING
if file_bytes:
    st.divider()
    st.markdown(f"**Loaded: {mime}**")
    
    default_cols = "First Name, Last Name, Email, Phone, Disability Type, Education, State"
    cols = st.text_area("Fields to Extract", value=default_cols).split(",")
    
    # ACTION: SCAN
    if st.button("🚀 Scan Document", type="primary"):
        with st.spinner("AI is reading..."):
            data = parse_document_dynamic(file_bytes, cols, mime, prompt_context="Youth Candidate Resume/ID")
            
            if "error" in data[0]:
                st.error(data[0]["error"])
            else:
                # SAVE TO SESSION STATE
                st.session_state["scanned_df"] = pd.DataFrame(data)

# 4. REVIEW & SAVE
if st.session_state["scanned_df"] is not None:
    st.divider()
    st.subheader("Verify Data")
    
    edited_df = st.data_editor(
        st.session_state["scanned_df"], 
        num_rows="dynamic", 
        key="editor"
    )
    
    col1, col2 = st.columns([3, 1])
    with col1:
        target_sheet = st.text_input("Sheet Name", value="YouthScan_Data")
    with col2:
        st.write("") 
        st.write("")
        save_btn = st.button("💾 Save to Cloud")
    
    if save_btn:
        with st.spinner("Saving to Google Drive..."):
            folder_id = st.secrets.get("youthscan", {}).get("folder_id")
            url = get_or_create_spreadsheet(target_sheet, folder_id)
            
            if url:
                data_to_save = edited_df.to_dict('records')
                if append_batch_to_sheet(url, data_to_save):
                    st.success("✅ Saved successfully!")
                    st.balloons()
