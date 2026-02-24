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
st.write(f"👋 Hi **{user['name']}**! Let's manage and message your employer contacts.")

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
default_sheet_name = f"JobScan_{v_email}"

target_sheet_name = st.text_input("Employer Sheet Name to Load:", value=default_sheet_name)

@st.cache_data(ttl=60, show_spinner=False)
def load_employers(sheet_name):
    # Secret folder reference is 'jobscan'
    fid = st.secrets.get("jobscan", {}).get("folder_id")
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
    df_employers, sheet_url = load_employers(target_sheet_name)

# 4. DASHBOARD INTERFACE
if df_employers.empty:
    st.warning(f"No employers found in '{target_sheet_name}'. Use 'JobScan' to add companies or check the sheet name.")
else:
    # A. METRICS
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Job Postings", len(df_employers))
    if 'Company Name' in df_employers.columns:
        col2.metric("Unique Companies", df_employers['Company Name'].nunique())
    if 'Location' in df_employers.columns:
        col3.metric("Locations", df_employers['Location'].nunique())

    st.divider()

    # B. SEARCH & SELECT
    search_term = st.text_input("Search Employers or Jobs (Type to filter list below)", "")
    
    # 1. Identify the Phone & Email Columns dynamically based on your sheet
    phone_col_name = 'Contact phone' if 'Contact phone' in df_employers.columns else None
    email_col_name = 'Contact Email' if 'Contact Email' in df_employers.columns else None
    
    # 2. Filter Data based on search
    if search_term:
        mask = df_employers.astype(str).apply(lambda x: x.str.contains(search_term, case=False)).any(axis=1)
        df_display = df_employers[mask].copy()
    else:
        df_display = df_employers.copy()

    # 3. Force string type on phone for cleaner display
    if phone_col_name and phone_col_name in df_display.columns:
        df_display[phone_col_name] = df_display[phone_col_name].astype(str).replace('nan', '')

    if df_display.empty:
        st.info("No employers match your search.")
    else:
        def make_label(row):
            company = str(row.get('Company Name', 'Unknown Company')).strip()
            role = str(row.get('Job Title', 'Unknown Role')).strip()
            location = str(row.get('Location', '')).strip()
            return f"{company} | {role} | {location}".strip()
        
        df_display['Select_Label'] = df_display.apply(make_label, axis=1)
        
        selected_label = st.selectbox("Select Employer/Job to Manage", df_display['Select_Label'].tolist())
        selected_idx = df_display[df_display['Select_Label'] == selected_label].index[0]
        selected_row = df_display.loc[selected_idx]

        # --- PROFILE SUMMARY CARD ---
        st.divider()
        st.subheader(f"🏢 {selected_row.get('Company Name', 'Company Not Provided')}")
        
        col_p1, col_p2, col_p3 = st.columns(3)
        emp_email = selected_row.get(email_col_name, '') if email_col_name else ''
        emp_phone_raw = selected_row.get(phone_col_name, '') if phone_col_name else ''
        
        # Displaying tailored data
        col_p1.write(f"**Email:** {emp_email if emp_email and str(emp_email).lower() != 'nan' else 'N/A'}")
        col_p1.write(f"**Phone:** {emp_phone_raw if emp_phone_raw and str(emp_phone_raw).lower() != 'nan' else 'N/A'}")
        col_p1.write(f"**Website:** {selected_row.get('Website Link', 'N/A')}")
        
        col_p2.write(f"**Job Title:** {selected_row.get('Job Title', 'N/A')}")
        col_p2.write(f"**Location:** {selected_row.get('Location', 'N/A')}")
        col_p2.write(f"**Salary:** {selected_row.get('Salary Range', 'N/A')}")
        
        col_p3.write(f"**Last Date:** {selected_row.get('Last date to apply', 'N/A')}")
        col_p3.write(f"**Experience:** {selected_row.get('Min Experience', 'N/A')}")
        col_p3.write(f"**PWD Friendly:** {selected_row.get('PWD', 'N/A')}")

        st.write("") 

        # Establish global variables for the tabs below
        clean_num = clean_phone_number(emp_phone_raw)
        contact_name = "Hiring Manager"  # No contact person explicitly listed, so we default to a formal title
        company_name = selected_row.get('Company Name', 'your company')
        job_role = selected_row.get('Job Title', 'open position')

        # --- THE TABS WORKSPACE ---
        tab_msg, tab_jd, tab_edit = st.tabs(["💬 Communication", "📄 Job Description", "✏️ Edit Details"])

        # ==========================================
        # TAB 1: COMMUNICATION
        # ==========================================
        with tab_msg:
            st.markdown("#### Message Employer")
            msg_type = st.radio("Message Type:", ["Candidate Referral Follow-up", "Custom Message"], horizontal=True)
            
            if msg_type == "Candidate Referral Follow-up":
                msg_body = f"Hi {contact_name}, following up on the {job_role} opening at {company_name}. Have you had a chance to review the profiles we shared from Youth4Jobs? Let us know if you need more candidates or want to schedule interviews."
                st.info(f"**Preview:** {msg_body}")
                
                col_wa, col_mail = st.columns(2)
                with col_wa:
                    if clean_num:
                        encoded_msg = urllib.parse.quote(msg_body)
                        wa_link = f"https://wa.me/{clean_num}?text={encoded_msg}"
                        st.link_button("📲 Send Follow-up via WhatsApp", wa_link, type="primary", use_container_width=True)
                    else:
                        st.button("📲 WhatsApp (No valid number)", disabled=True, use_container_width=True)

                with col_mail:
                    if emp_email and "@" in str(emp_email):
                        subject = f"Youth4Jobs Follow-up: {job_role} candidates for {company_name}"
                        full_email_body = f"Hi {contact_name},\n\nFollowing up on the {job_role} opening at {company_name}. Have you had a chance to review the candidate profiles we recently shared?\n\nPlease let us know if you would like us to schedule interviews or if you need additional profiles.\n\nThank you,\nYouth4Jobs Team"
                        params = urllib.parse.urlencode({'subject': subject, 'body': full_email_body})
                        mailto_link = f"mailto:{emp_email}?{params}"
                        st.link_button("📧 Send Follow-up via Email", mailto_link, use_container_width=True)
                    else:
                        st.button("📧 Email (No valid email)", disabled=True, use_container_width=True)
                        
            elif msg_type == "Custom Message":
                custom_subject = st.text_input("Subject (For Email Only):", value=f"Update regarding {job_role} from Youth4Jobs")
                custom_text = st.text_area("Draft your message:", height=150, value=f"Hi {contact_name},\n\n")
                
                col_cwa, col_cmail = st.columns(2)
                with col_cwa:
                    if clean_num:
                        encoded_custom = urllib.parse.quote(custom_text)
                        custom_wa_link = f"https://wa.me/{clean_num}?text={encoded_custom}"
                        st.link_button("📲 Send via WhatsApp", custom_wa_link, type="primary", use_container_width=True)
                    else:
                        st.button("📲 WhatsApp (No valid number)", disabled=True, use_container_width=True)
                
                with col_cmail:
                    if emp_email and "@" in str(emp_email):
                        params = urllib.parse.urlencode({'subject': custom_subject, 'body': custom_text})
                        custom_mailto = f"mailto:{emp_email}?{params}"
                        st.link_button("📧 Send via Email", custom_mailto, use_container_width=True)
                    else:
                        st.button("📧 Email (No valid email)", disabled=True, use_container_width=True)

        # ==========================================
        # TAB 2: JOB DESCRIPTION GENERATOR
        # ==========================================
        with tab_jd:
            st.markdown("#### Job Description Overview")
            st.write("A simple text JD generated from the employer's available data to easily share with candidates.")
            
            # Build the simple markdown JD with the actual column names
            jd_company = str(company_name).upper()
            jd_role = str(job_role)
            jd_loc = str(selected_row.get('Location', 'Location Not Provided'))
            jd_salary = str(selected_row.get('Salary Range', 'Not Disclosed'))
            jd_exp = str(selected_row.get('Min Experience', 'Not Specified'))
            jd_skills = str(selected_row.get('Required Skills', 'Not Specified'))
            jd_last_date = str(selected_row.get('Last date to apply', 'N/A'))
            jd_website = str(selected_row.get('Website Link', 'N/A'))
            jd_pwd = str(selected_row.get('PWD', 'N/A'))
            
            simple_jd = f"""
JOB OPENING: {jd_role.upper()}
--------------------------------------------------
Company:        {jd_company}
Location:       {jd_loc}
Salary Range:   {jd_salary}
Experience:     {jd_exp}
Last Date:      {jd_last_date}

REQUIREMENTS
--------------------------------------------------
Skills Needed:  {jd_skills}
PWD Supported:  {jd_pwd}

MORE DETAILS
--------------------------------------------------
Website Link:   {jd_website}

Please contact your Youth4Jobs coordinator if you are interested in this role!
"""
            
            # Display it in a nice container
            st.text_area("JD Preview", value=simple_jd.strip(), height=380, disabled=True)
            
            st.markdown("#### Share Job Description")
            col_dl, col_rwa, col_rmail = st.columns(3)
            
            with col_dl:
                st.download_button(
                    label="📥 Download Text File",
                    data=simple_jd.strip(),
                    file_name=f"{jd_company.replace(' ', '_')}_{jd_role.replace(' ', '_')}_JD.txt",
                    mime="text/plain",
                    type="primary",
                    use_container_width=True
                )
            
            with col_rwa:
                # Share JD internally or to candidates
                wa_jd_text = f"New Job Opening via Youth4Jobs!\n\n{simple_jd.strip()}"
                encoded_wa_jd = urllib.parse.quote(wa_jd_text)
                wa_jd_link = f"https://wa.me/?text={encoded_wa_jd}" 
                st.link_button("📲 Forward via WhatsApp", wa_jd_link, use_container_width=True)

            with col_rmail:
                # Forward JD via default mail client
                r_subject = f"Job Opening: {jd_role} at {jd_company}"
                r_body = f"Please see the job details below:\n\n{simple_jd.strip()}"
                r_params = urllib.parse.urlencode({'subject': r_subject, 'body': r_body})
                r_mailto = f"mailto:?{r_params}" 
                st.link_button("📧 Forward via Email", r_mailto, use_container_width=True)

        # ==========================================
        # TAB 3: EDIT DETAILS
        # ==========================================
        with tab_edit:
            st.markdown("#### Update Database")
            st.caption("Update the fields below and press Save Changes to sync with Google Drive.")
            
            with st.form("edit_employer_form"):
                updated_data = {}
                # Dynamically generate text inputs for all original columns (skip Select_Label)
                for col in df_employers.columns:
                    if col != 'Select_Label':
                        current_val = str(selected_row[col]) if pd.notna(selected_row[col]) and str(selected_row[col]).lower() != 'nan' else ""
                        updated_data[col] = st.text_input(label=col, value=current_val)
                    
                submitted = st.form_submit_button("Save Changes", type="primary")
                
                if submitted:
                    if sheet_url:
                        with st.spinner("Syncing to Google Drive..."):
                            for col in df_employers.columns:
                                if col != 'Select_Label':
                                    df_employers.at[selected_idx, col] = updated_data[col]
                            
                            # Drop the temporary display column before saving
                            df_to_save = df_employers.drop(columns=['Select_Label'], errors='ignore')
                            
                            if overwrite_sheet_with_df(sheet_url, df_to_save):
                                st.success("Database Updated Successfully!")
                                st.cache_data.clear()
                                time.sleep(2)
                                st.rerun()
                            else:
                                st.error("Save Failed. Please try again.")
