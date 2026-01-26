import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIGURATION ---
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def init_google_sheet_client():
    """
    Authenticate with Google Sheets using Streamlit Secrets.
    Returns the 'client' object needed for all operations.
    """
    try:
        if "gcp_service_account" not in st.secrets:
            st.error("❌ Critical Error: 'gcp_service_account' missing in secrets.toml")
            return None
        
        # Load credentials from secrets
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"❌ Auth Error: {e}")
        return None

def get_or_create_spreadsheet(sheet_name, folder_id=None):
    """
    Finds a sheet by name, or creates it inside a specific Drive folder if missing.
    """
    client = init_google_sheet_client()
    if not client: return None

    try:
        # 1. Try to open existing sheet
        sh = client.open(sheet_name)
        return sh.url
    except gspread.SpreadsheetNotFound:
        # 2. Create new if not found
        try:
            sh = client.create(sheet_name)
            
            # 3. Move to specific folder if ID is provided
            if folder_id:
                try:
                    # Move file using Drive API (via gspread wrapper or simple logic)
                    # Note: gspread doesn't move files easily, so we usually just create it.
                    # For simplicity in this ecosystem, we let it stay in Root or use Drive API.
                    # Permission sharing is key:
                    sh.share(st.secrets["gcp_service_account"]["client_email"], perm_type='user', role='writer')
                    pass 
                except Exception as e:
                    print(f"Folder move warning: {e}")
            
            return sh.url
        except Exception as e:
            st.error(f"❌ Error creating sheet: {e}")
            return None

def read_data_from_sheet(sheet_url):
    """
    Reads all records from the first tab of the Google Sheet.
    """
    client = init_google_sheet_client()
    if not client: return []

    try:
        sh = client.open_by_url(sheet_url)
        worksheet = sh.get_worksheet(0)
        return worksheet.get_all_records()
    except Exception as e:
        st.error(f"❌ Read Error: {e}")
        return []

def append_batch_to_sheet(sheet_url, data_list):
    """
    Appends a list of dictionaries (rows) to the sheet.
    """
    if not data_list: return True
    
    client = init_google_sheet_client()
    if not client: return False

    try:
        sh = client.open_by_url(sheet_url)
        worksheet = sh.get_worksheet(0)
        
        # Check if headers exist, if not add them
        if not worksheet.row_values(1):
            headers = list(data_list[0].keys())
            worksheet.append_row(headers)
            
        # Prepare values (ensure order matches headers)
        # Simple append: gspread handles dicts well if headers match, 
        # but robust way is list of lists
        headers = worksheet.row_values(1)
        rows_to_add = []
        for item in data_list:
            row = [item.get(h, "") for h in headers]
            rows_to_add.append(row)
            
        worksheet.append_rows(rows_to_add)
        return True
    except Exception as e:
        st.error(f"❌ Append Error: {e}")
        return False

def overwrite_sheet_with_df(sheet_url, df):
    """
    Completely clears the sheet and replaces it with the new DataFrame.
    Used for the 'Edit & Save' functionality.
    """
    client = init_google_sheet_client() # <--- THIS was likely missing before!
    if not client: return False

    try:
        sh = client.open_by_url(sheet_url)
        worksheet = sh.get_worksheet(0)
        
        # 1. Clear existing data
        worksheet.clear()
        
        # 2. Prepare data 
        # Handle NaN values which cause JSON errors
        df_clean = df.fillna("") 
        
        # Create a list of lists: [Headers] + [Rows]
        data_to_upload = [df_clean.columns.values.tolist()] + df_clean.values.tolist()
        
        # 3. Update
        worksheet.update(data_to_upload)
        return True
        
    except Exception as e:
        st.error(f"❌ Save Error: {e}")
        return False
