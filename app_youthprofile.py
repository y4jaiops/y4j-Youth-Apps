import streamlit as st
import pandas as pd
import time
import urllib.parse
from logic.style_manager import set_app_theme
from logic.auth_user import login_required
from logic.logic_sheets import get_or_create_spreadsheet, read_data_from_sheet, overwrite_sheet_with_df

# 1. SETUP
set_app_theme("profile") # 🔵 Blue Vibe
user = login_required()

st.title("🔵 YouthProfile Manager")
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
    st.warning("⚠️ No candidates found. Use 'YouthScan' to add people.")
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
        search_term = st.text_input("🔍 Search Candidates", "")
    with col_action:
        # Action Mode Toggle
        action_mode = st.radio("Mode:", ["Edit Data", "Send Survey"], horizontal=True)

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

    # 3. FORCE STRING TYPE (Crucial for editing)
    if phone_col_name and phone_col_name in df_display.columns:
        df_display[phone_col_name] = df_display[phone_col_name].astype(str).replace('nan', '')

    # --- MODE 1: EDIT DATA ---
    if action_mode == "Edit Data":
        st.caption("📝 **Edit Mode:** Double-click cells to fix typos. Click Save below.")
        
        # Build the Column Configuration dynamically
        my_column_config = {}
        if phone_col_name:
            my_column_config[phone_col_name] = st.column_config.TextColumn(
                label="Phone Number",
                help="Enter phone number (Text allowed)",
                default="",
                width="medium"
            )

        edited_df = st.data_editor(
            df_display, 
            num_rows="dynamic", 
            use_container_width=True,
            key="profile_editor",
            column_config=my_column_config
        )

        st.write("")
        if st.button("💾 Save Changes", type="primary"):
            if sheet_url:
                with st.spinner("Syncing to Google Drive..."):
                    if search_term:
                        st.error("⚠️ Safety Lock: Please clear the Search Box before Saving.")
                    else:
                        if overwrite_sheet_with_df(sheet_url, edited_df):
                            st.success("✅ Database Updated!")
                            st.cache_data.clear()
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error("❌ Save Failed.")
    
    # --- MODE 2: SEND SURVEY (WHATSAPP & EMAIL) ---
    elif action_mode == "Send Survey":
        st.caption("📱 **Survey Mode:** Select a candidate to contact them.")
        
        # We use a dataframe with a selection checkbox
        target_cols = ['First Name', 'Last Name', 'Email']
        if phone_col_name: target_cols.append(phone_col_name)
        
        display_cols = [c for c in target_cols if c in df_display.columns]
        
        event = st.dataframe(
            df_display[display_cols],
            use_container_width=True,
            on_select="rerun",
            selection_mode="single-row"
        )
        
        if event.selection.rows:
            idx = event.selection.rows[0]
            selected_row = df_display.iloc[idx]
            
            cand_name = selected_row.get('First Name', 'Candidate')
            cand_email = selected_row.get('Email', '')
            
            # Get phone safely
            cand_phone = ""
            if phone_col_name:
                cand_phone = selected_row.get(phone_col_name, '')
            
            st.divider()
            st.subheader(f"📨 Contact: {cand_name}")
            
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
                    
                    st.success(f"📱 Mobile: +{clean_num}")
                    st.link_button("💬 Open WhatsApp", wa_link, type="primary")
                else:
                    st.warning("⚠️ No valid Phone Number.")

            # 2. EMAIL BUTTON
            with col_mail:
                if cand_email and "@" in str(cand_email):
                    # Create Mailto link
                    subject = "Feedback Request: Youth4Jobs Survey"
                    full_email_body = f"Hi {cand_name},\n\nWe are updating our records and would love your input.\nPlease fill out this survey:\n\n{SURVEY_LINK}\n\nThank you,\nYouth4Jobs Team"
                    
                    email_params = {'subject': subject, 'body': full_email_body}
                    params = urllib.parse.urlencode(email_params)
                    mailto_link = f"mailto:{cand_email}?{params}"
                    
                    st.info(f"📧 Email: {cand_email}")
                    st.link_button("📤 Open Draft Email", mailto_link)
                else:
                    st.warning("⚠️ No valid Email found.")
