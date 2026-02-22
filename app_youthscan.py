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
    # NEW: Added "Paste Text" to the options
    input_mode = st.radio(
        "Select Document Source:",
        ["Browse from Device", "Download from Google Drive", "Take Photo from Camera", "Paste Text"],
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
                
    
    #NEW Logic for Paste Text and Clear Text
    elif input_mode == "Paste Text":
        st.info("Paste the raw text of one or more resumes below.")
        
        # 1. Define the callback function right here
        def clear_text_callback():
            st.session_state["paste_area"] = ""
            st.session_state["active_file"] = {"data": None, "mime": None}
            st.session_state["scanned_df"] = None
            
        # 2. The text area tied to the "paste_area" key
        pasted_text = st.text_area("Resume Text", height=250, key="paste_area")
        
        # 3. Layout the buttons
        col1, col2 = st.columns([1, 5])
        
        with col1:
            if st.button("Load Text"):
                if pasted_text.strip():
                    st.session_state["active_file"] = {"data": pasted_text.encode("utf-8"), "mime": "text/plain"}
                    st.success("✅ Text Loaded Successfully!")
                else:
                    st.warning("Please paste some text first.")
                    
        with col2:
            # 4. Bind the callback to the button using on_click (No st.rerun() needed!)
            st.button("Clear Text", on_click=clear_text_callback)
            
    
# 5. PROCESSING
active_file = st.session_state["active_file"]

if active_file["data"] is not None:
    st.divider()
    if "image" in active_file["mime"]:
        st.image(active_file["data"], width=300)
    # NEW: Add a small preview specifically for text so the user knows it's ready
    elif active_file["mime"] == "text/plain":
        st.markdown("**Text Loaded Preview:**")
        preview_text = active_file["data"].decode("utf-8")
        st.caption(preview_text[:300] + ("..." if len(preview_text) > 300 else ""))
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
                # Reset index to ensure it's a clean 0-based index for logic
                st.session_state["scanned_df"] = pd.DataFrame(result).reset_index(drop=True)

# 6. VERIFY & SAVE SECTION (Dropdown Edit Mode)
if st.session_state["scanned_df"] is not None:
    st.divider()
    st.subheader("Verify & Save Data")
    
    df = st.session_state["scanned_df"]
    
    # 1. Accessible Static Table Display
    st.markdown("**Review Extracted Data:**")
    
    display_df = df.copy()
    display_df.index = display_df.index + 1
    st.table(display_df) 
    
    st.divider()
    st.markdown("**Edit Data (If Needed):**")
    
    # 2. Candidate Selection Dropdown
    def make_dropdown_label(idx, row):
        fname = str(row.get('First Name', '')) if 'First Name' in row and pd.notna(row.get('First Name')) else ''
        lname = str(row.get('Last Name', '')) if 'Last Name' in row and pd.notna(row.get('Last Name')) else ''
        full_name = f"{fname} {lname}".strip()
        return f"Candidate {idx + 1}: {full_name}" if full_name else f"Candidate {idx + 1}"
        
    # Create labels mapping to the row indices
    dropdown_labels = [make_dropdown_label(i, r) for i, r in df.iterrows()]
    
    selected_label = st.selectbox("Select a candidate to correct:", dropdown_labels)
    selected_idx = dropdown_labels.index(selected_label)
    selected_row = df.loc[selected_idx]
    
    # 3. Accessible Edit Form for the Selected Candidate
    with st.form("edit_candidate_form"):
        st.caption(f"Editing: **{selected_label}**")
        
        updated_data = {}
        for col in df.columns:
            current_val = str(selected_row[col]) if pd.notna(selected_row[col]) else ""
            updated_data[col] = st.text_input(label=col, value=current_val)
            
        apply_edits = st.form_submit_button("Apply Edits to Table")
        
        if apply_edits:
            for col in df.columns:
                st.session_state["scanned_df"].at[selected_idx, col] = updated_data[col]
            st.success(f"Updated {selected_label} in the table above!")
            time.sleep(1)
            st.rerun()


    st.divider()
    
    # 4. Final Save to Google Drive Controls
    st.markdown("**Finalize & Save:**")
    col1, col2 = st.columns([3, 1])
    with col1:
        sheet_name = st.text_input("Google Sheet Name (Saving Destination)", value="YouthScan_Data")
    with col2:
        st.write("") # Spacer
        st.write("") # Spacer
        final_save = st.button("Save Batch to Google Drive", type="primary")
        
    # Make sure this 'if' lines up perfectly with the 'with col1:' above it!
    if final_save:
        with st.spinner("Saving all records to Google Drive..."):
            fid = st.secrets.get("youthscan", {}).get("folder_id")
            url = get_or_create_spreadsheet(sheet_name, fid)
            
            # Convert dataframe to dictionary records for appending
            records_to_save = st.session_state["scanned_df"].to_dict('records')
            
            if url and append_batch_to_sheet(url, records_to_save):
                st.success("✅ Saved successfully!")
                
                # Visual Feedback
                st.balloons() 
                
                # Audio Feedback
                try:
                    st.audio("success.mp3", autoplay=True)
                except Exception as e:
                    pass 
                
                time.sleep(2.5) 
                
                full_reset() 
                st.rerun()

