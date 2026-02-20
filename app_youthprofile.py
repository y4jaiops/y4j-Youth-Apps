import streamlit as st
import pandas as pd
import time
import urllib.parse
from logic.style_manager import set_app_theme
from logic.auth_user import login_required
from logic.logic_sheets import get_or_create_spreadsheet, read_data_from_sheet, overwrite_sheet_with_df

# 1. SETUP
set_app_theme("profile") 
user = login_required()

st.title("YouthProfile Manager")
st.write(f"Logged in as: **{user['name']}**")

# --- CONFIGURATION ---
SURVEY_LINK = "https://forms.gle/YOUR_ACTUAL_FORM_ID" 

# 2. HELPER FUNCTIONS
def clean_phone_number(phone_raw):
    """
    Cleans phone number for WhatsApp URL.
    Removes dashes, spaces, brackets. Ensures country code (defaults to India +91).
    """
    if pd.isna(phone_raw): return None
    
    # Remove non-digit characters
    clean = ''.join(filter(str.isdigit, str(phone_raw)))
    
    if not clean: return None
    
    # Append country code if it looks like a 10-digit Indian number
    if len(clean) == 10:
        return "91" + clean
        
    return clean

# 3. LOAD DATA
@st.cache_data(ttl=60)
def load_candidates():
    fid = st.secrets.get("youthscan", {}).get("folder_id")
    url = get_or_create_spreadsheet("YouthScan_Data", fid)
    
    if url:
        data = read_data_from_sheet(url)
        if data:
            df = pd.DataFrame(data)
            return df, url
            
    return pd.DataFrame(), url

# Load initial data
df_candidates, sheet_url = load_candidates()

# 4. DASHBOARD INTERFACE
if df_candidates.empty:
    st.warning("No candidates found. Use 'YouthScan' to add people.")
else:
    # A. METRICS
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Candidates", len(df_candidates))
    if 'State' in df_candidates.columns:
        col2.metric("Locations", df_candidates['State'].nunique())
    if 'Disability Type' in df_candidates.columns:
        col3.metric("Disability Types", df_candidates['Disability Type'].nunique())

    st.divider()

    # B. SEARCH & ACTION
    col_search, col_action = st.columns([3, 1])
    with col_search:
        # Added instructional text to the label for screen readers
        search_term = st.text_input("Search Candidates (Type to filter list below)", "")
    with col_action:
        action_mode = st.radio("Select Mode:", ["Edit Data", "Send Survey"])

    # C. DATA DISPLAY & PREP
    # 1. Identify the Phone Column dynamically
    phone_col_name = None
    for col in df_candidates.columns:
        if "phone" in col.lower() or "mobile" in col.lower():
            phone_col_name = col
            break
    
    # 2. Filter Data based on search
    if search_term:
        mask = df_candidates.astype(str).apply(lambda x: x.str.contains(search_term, case=False)).any(axis=1)
        df_display = df_candidates[mask].copy()
    else:
        df_display = df_candidates.copy()

    # 3. FORCE STRING TYPE
    if phone_col_name and phone_col_name in df_display.columns:
        df_display[phone_col_name] = df_display[phone_col_name].astype(str).replace('nan', '')

    # --- ACCESSIBLE SELECTION MECHANISM ---
    if df_display.empty:
        st.info("No candidates match your search.")
    else:
        # Create a readable string for the selectbox dropdown
        def make_label(row):
            name = str(row.get('First Name', 'Unknown')) + " " + str(row.get('Last Name', ''))
            phone = str(row.get(phone_col_name, '')) if phone_col_name else ''
            return f"{name.strip()} - {phone}"
        
        df_display['Select_Label'] = df_display.apply(make_label, axis=1)
        
        # The selectbox is fully keyboard-navigable and screen-reader friendly
        selected_label = st.selectbox("Select Candidate to Manage", df_display['Select_Label'].tolist())
        selected_idx = df_display[df_display['Select_Label'] == selected_label].index[0]
        selected_row = df_display.loc[selected_idx]

        st.divider()

        # --- MODE 1: EDIT DATA ---
        if action_mode == "Edit Data":
            st.subheader("Edit Candidate Details")
            st.caption("Update the fields below and press Save Changes.")
            
            # Using a standard form instead of a data grid
            with st.form("edit_candidate_form"):
                updated_data = {}
                # Dynamically generate text inputs for all columns (skipping the temp Select_Label)
                for col in df_candidates.columns:
                    current_val = str(selected_row[col]) if pd.notna(selected_row[col]) else ""
                    updated_data[col] = st.text_input(label=col, value=current_val)
                    
                submitted = st.form_submit_button("Save Changes", type="primary")
                
                if submitted:
                    if sheet_url:
                        with st.spinner("Syncing to Google Drive..."):
                            # Update the main dataframe at the specific index
                            for col in df_candidates.columns:
                                df_candidates.at[selected_idx, col] = updated_data[col]
                            
                            if overwrite_sheet_with_df(sheet_url, df_candidates):
                                st.success("Database Updated Successfully!")
                                st.cache_data.clear()
                                time.sleep(2)
                                st.rerun()
                            else:
                                st.error("Save Failed. Please try again.")
        
        # --- MODE 2: SEND SURVEY (WHATSAPP & EMAIL) ---
        elif action_mode == "Send Survey":
            cand_name = selected_row.get('First Name', 'Candidate')
            cand_email = selected_row.get('Email', '')
            cand_phone = selected_row.get(phone_col_name, '') if phone_col_name else ''
            
            st.subheader(f"Contact Options for {cand_name}")
            
            # THE MESSAGE CONTENT
            msg_body = f"Hi {cand_name}, please help us by filling out this Youth4Jobs survey: {SURVEY_LINK} . Thanks!"
            
            col_wa, col_mail = st.columns(2)
            
            # 1. WHATSAPP BUTTON
            with col_wa:
                clean_num = clean_phone_number(cand_phone)
                if clean_num:
                    # Create wa.me link
                    encoded_msg = urllib.parse.quote(msg_body)
                    wa_link = f"https://wa.me/{clean_num}?text={encoded_msg}"
                    
                    st.info(f"Mobile: +{clean_num}")
                    st.link_button("Open WhatsApp", wa_link, type="primary")
                else:
                    st.warning("No valid Phone Number available.")

            # 2. EMAIL BUTTON
            with col_mail:
                if cand_email and "@" in str(cand_email):
                    # Create Mailto link
                    subject = "Feedback Request: Youth4Jobs Survey"
                    full_email_body = f"Hi {cand_name},\n\nWe are updating our records and would love your input.\nPlease fill out this survey:\n\n{SURVEY_LINK}\n\nThank you,\nYouth4Jobs Team"
                    
                    email_params = {'subject': subject, 'body': full_email_body}
                    params = urllib.parse.urlencode(email_params)
                    mailto_link = f"mailto:{cand_email}?{params}"
                    
                    st.info(f"Email: {cand_email}")
                    st.link_button("Open Draft Email", mailto_link)
                else:
                    st.warning("No valid Email available.")
