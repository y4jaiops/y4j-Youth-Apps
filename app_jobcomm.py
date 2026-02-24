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
        col_p1.write(f"**
