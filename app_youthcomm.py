import streamlit as st
import pandas as pd
import time
import urllib.parse
from logic.style_manager import set_app_theme
from logic.auth_user import login_required
from logic.logic_sheets import get_or_create_spreadsheet, read_data_from_sheet, overwrite_sheet_with_df

# 1. SETUP
set_app_theme("youthcomm") 
user = login_required()

st.title("Youth Communication Manager")
st.write(f"👋 Hi **{user['name']}**! Let's manage and message candidates.")

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
        
        df_display['Select_Label'] = df_
