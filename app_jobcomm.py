import streamlit as st
import pandas as pd
import time
import urllib.parse
from logic.style_manager import set_app_theme
from logic.auth_user import login_required
from logic.logic_sheets import get_or_create_spreadsheet, read_data_from_sheet, overwrite_sheet_with_df

# 1. SETUP
set_app_theme("jobcomm") 
user = login_required()

st.title("Employer Communication Manager")
st.write(f"👋 Hi **{user['name']}**! Let's manage and message employer.")

# --- CONFIGURATION ---
SURVEY_LINK = "https://forms.gle/YOUR_ACTUAL_FORM_ID" 

# 2. HELPER FUNCTIONS
def clean_phone_number(phone_raw):
    """
    Cleans phone number for WhatsApp URL.
    Removes dashes, spaces, brackets. Ensures country code (defaults to India +91).
    """
    if pd.isna(phone_raw): return None
    
    clean = ''.join(filter(str.isdigit, str(phone_raw)))
    if not clean: return None
    
    if len(clean) == 10:
        return "91" + clean
        
    return clean

# 3. CONFIGURE & LOAD DATA
st.subheader("📂 Data Source")

# Dynamically generate the default sheet name based on the logged-in user
v_email = user.get("email") if user.get("email") else "volunteer"
default_sheet_name = f"YouthScan_{v_email}"

target_sheet_name = st.text_input("Candidate Sheet Name to Load:", value=default_sheet_name)

@st.cache_data(ttl=60, show_spinner=False)
def load_candidates(sheet_name):
    fid = st.secrets.get("youthscan", {}).get("folder_id")
    url = get_or_create_spreadsheet(sheet_name, fid)
    
    if url:
        data = read_data_from_sheet(url)
        if data:
            df = pd.DataFrame(data)
            
            # --- Clean column names and drop duplicates ---
            df.columns = df.columns.astype(str).str.strip()
            df = df.loc[:, ~df.columns.duplicated()]
            
            return df, url
            
    return pd.DataFrame(), url

# Load initial data
with st.spinner(f"Loading data from '{target_sheet_name}'..."):
    df_candidates, sheet_url = load_candidates(target_sheet_name)

# 4. DASHBOARD INTERFACE
if df_candidates.empty:
    st.warning(f"No candidates found in '{target_sheet_name}'. Use 'YouthScan' to add people or check the sheet name.")
else:
    # A. METRICS
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Candidates", len(df_candidates))
    if 'State' in df_candidates.columns:
        col2.metric("Locations", df_candidates['State'].nunique())
    if 'Disability Type' in df_candidates.columns:
        col3.metric("Disability Types", df_candidates['Disability Type'].nunique())

    st.divider()

    # B. SEARCH & SELECT
    search_term = st.text_input("Search Candidates (Type to filter list below)", "")
    
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

    # 3. Force string type on phone for cleaner display
    if phone_col_name and phone_col_name in df_display.columns:
        df_display[phone_col_name] = df_display[phone_col_name].astype(str).replace('nan', '')

    if df_display.empty:
        st.info("No candidates match your search.")
    else:
        def make_label(row):
            fname = str(row.get('First Name', 'Unknown')).strip()
            lname = str(row.get('Last Name', '')).strip()
            phone = str(row.get(phone_col_name, '')).strip() if phone_col_name else ''
            return f"{fname} {lname} - {phone}".strip()
        
        df_display['Select_Label'] = df_display.apply(make_label, axis=1)
        
        selected_label = st.selectbox("Select Candidate to Manage", df_display['Select_Label'].tolist())
        selected_idx = df_display[df_display['Select_Label'] == selected_label].index[0]
        selected_row = df_display.loc[selected_idx]

        # --- PROFILE SUMMARY CARD ---
        st.divider()
        st.subheader(f"👤 {selected_row.get('First Name', '')} {selected_row.get('Last Name', '')}")
        
        col_p1, col_p2, col_p3 = st.columns(3)
        cand_email = selected_row.get('Email', '')
        cand_phone_raw = selected_row.get(phone_col_name, '') if phone_col_name else ''
        
        col_p1.write(f"**Email:** {cand_email if cand_email else 'N/A'}")
        col_p1.write(f"**Phone:** {cand_phone_raw if cand_phone_raw else 'N/A'}")
        col_p2.write(f"**Location:** {selected_row.get('State', 'N/A')}")
        col_p2.write(f"**Education:** {selected_row.get('Qualification', 'N/A')}")
        col_p3.write(f"**Disability:** {selected_row.get('Disability Type', 'N/A')}")
        col_p3.write(f"**Skills:** {selected_row.get('Skills', 'N/A')}")

        st.write("") 

        # Establish global variables for the tabs below
        clean_num = clean_phone_number(cand_phone_raw)
        cand_name = selected_row.get('First Name', 'Candidate')

        # --- THE TABS WORKSPACE ---
        tab_msg, tab_resume, tab_edit = st.tabs(["💬 Communication", "📄 Resume", "✏️ Edit Profile"])

        # ==========================================
        # TAB 1: COMMUNICATION
        # ==========================================
        with tab_msg:
            st.markdown("#### Message Candidate")
            msg_type = st.radio("Message Type:", ["Quick Survey Link", "Custom Message"], horizontal=True)
            
            if msg_type == "Quick Survey Link":
                msg_body = f"Hi {cand_name}, please help us by filling out this Youth4Jobs survey: {SURVEY_LINK} . Thanks!"
                st.info(f"**Preview:** {msg_body}")
                
                col_wa, col_mail = st.columns(2)
                with col_wa:
                    if clean_num:
                        encoded_msg = urllib.parse.quote(msg_body)
                        wa_link = f"https://wa.me/{clean_num}?text={encoded_msg}"
                        st.link_button("📲 Send Survey via WhatsApp", wa_link, type="primary", use_container_width=True)
                    else:
                        st.button("📲 WhatsApp (No valid number)", disabled=True, use_container_width=True)

                with col_mail:
                    if cand_email and "@" in str(cand_email):
                        subject = "Feedback Request: Youth4Jobs Survey"
                        full_email_body = f"Hi {cand_name},\n\nWe are updating our records and would love your input.\nPlease fill out this survey:\n\n{SURVEY_LINK}\n\nThank you,\nYouth4Jobs Team"
                        params = urllib.parse.urlencode({'subject': subject, 'body': full_email_body})
                        mailto_link = f"mailto:{cand_email}?{params}"
                        st.link_button("📧 Send Survey via Email", mailto_link, use_container_width=True)
                    else:
                        st.button("📧 Email (No valid email)", disabled=True, use_container_width=True)
                        
            elif msg_type == "Custom Message":
                custom_subject = st.text_input("Subject (For Email Only):", value="Message from Youth4Jobs")
                custom_text = st.text_area("Draft your message:", height=150, value=f"Hi {cand_name},\n\n")
                
                col_cwa, col_cmail = st.columns(2)
                with col_cwa:
                    if clean_num:
                        encoded_custom = urllib.parse.quote(custom_text)
                        custom_wa_link = f"https://wa.me/{clean_num}?text={encoded_custom}"
                        st.link_button("📲 Send via WhatsApp", custom_wa_link, type="primary", use_container_width=True)
                    else:
                        st.button("📲 WhatsApp (No valid number)", disabled=True, use_container_width=True)
                
                with col_cmail:
                    if cand_email and "@" in str(cand_email):
                        params = urllib.parse.urlencode({'subject': custom_subject, 'body': custom_text})
                        custom_mailto = f"mailto:{cand_email}?{params}"
                        st.link_button("📧 Send via Email", custom_mailto, use_container_width=True)
                    else:
                        st.button("📧 Email (No valid email)", disabled=True, use_container_width=True)

        # ==========================================
        # TAB 2: RESUME GENERATOR
        # ==========================================
        with tab_resume:
            st.markdown("#### Candidate Resume Overview")
            st.write("A simple text resume generated from the candidate's available data.")
            
            # Build the simple markdown resume
            r_name = f"{selected_row.get('First Name', '')} {selected_row.get('Last Name', '')}".strip()
            r_loc = selected_row.get('State', 'Location Not Provided')
            r_phone = cand_phone_raw if cand_phone_raw else 'Phone Not Provided'
            r_email = cand_email if cand_email else 'Email Not Provided'
            r_edu = selected_row.get('Qualification', 'N/A')
            r_skills = selected_row.get('Skills', 'N/A')
            r_disability = selected_row.get('Disability Type', 'N/A')
            
            simple_resume = f"""
{r_name.upper()}
--------------------------------------------------
Location:   {r_loc}
Phone:      {r_phone}
Email:      {r_email}
Disability: {r_disability}

PROFESSIONAL SUMMARY
--------------------------------------------------
Dedicated candidate seeking opportunities matching my skills and qualifications.

EDUCATION & QUALIFICATIONS
--------------------------------------------------
* {r_edu}

KEY SKILLS
--------------------------------------------------
* {r_skills}
"""
            
            # Display it in a nice container
            st.text_area("Resume Preview", value=simple_resume.strip(), height=350, disabled=True)
            
            st.markdown("#### Share Resume")
            col_dl, col_rwa, col_rmail = st.columns(3)
            
            with col_dl:
                st.download_button(
                    label="📥 Download Text File",
                    data=simple_resume.strip(),
                    file_name=f"{r_name.replace(' ', '_')}_Resume.txt",
                    mime="text/plain",
                    type="primary",
                    use_container_width=True
                )
            
            with col_rwa:
                if clean_num:
                    wa_resume_text = f"Hi {cand_name}, here is the text version of your resume generated by Youth4Jobs:\n\n{simple_resume.strip()}"
                    encoded_wa_resume = urllib.parse.quote(wa_resume_text)
                    wa_resume_link = f"https://wa.me/{clean_num}?text={encoded_wa_resume}"
                    st.link_button("📲 Send via WhatsApp", wa_resume_link, use_container_width=True)
                else:
                    st.button("📲 WhatsApp (No number)", disabled=True, use_container_width=True)

            with col_rmail:
                if cand_email and "@" in str(cand_email):
                    r_subject = f"Your Youth4Jobs Resume - {r_name}"
                    r_body = f"Hi {cand_name},\n\nPlease find the text version of your resume below:\n\n{simple_resume.strip()}"
                    r_params = urllib.parse.urlencode({'subject': r_subject, 'body': r_body})
                    r_mailto = f"mailto:{cand_email}?{r_params}"
                    st.link_button("📧 Send via Email", r_mailto, use_container_width=True)
                else:
                    st.button("📧 Email (No email)", disabled=True, use_container_width=True)

        # ==========================================
        # TAB 3: EDIT PROFILE
        # ==========================================
        with tab_edit:
            st.markdown("#### Update Database")
            st.caption("Update the fields below and press Save Changes to sync with Google Drive.")
            
            with st.form("edit_candidate_form"):
                updated_data = {}
                # Dynamically generate text inputs for all original columns (skip Select_Label)
                for col in df_candidates.columns:
                    current_val = str(selected_row[col]) if pd.notna(selected_row[col]) else ""
                    updated_data[col] = st.text_input(label=col, value=current_val)
                    
                submitted = st.form_submit_button("Save Changes", type="primary")
                
                if submitted:
                    if sheet_url:
                        with st.spinner("Syncing to Google Drive..."):
                            for col in df_candidates.columns:
                                df_candidates.at[selected_idx, col] = updated_data[col]
                            
                            if overwrite_sheet_with_df(sheet_url, df_candidates):
                                st.success("Database Updated Successfully!")
                                st.cache_data.clear()
                                time.sleep(2)
                                st.rerun()
                            else:
                                st.error("Save Failed. Please try again.")
