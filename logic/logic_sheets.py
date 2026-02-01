import streamlit as st
import gspread
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

# --- CONFIGURATION ---
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def init_google_sheet_client():
    """
    Authenticate using OAuth 2.0 Refresh Token (Acts as the User, not a Service Account).
    This bypasses Service Account storage quotas.
    """
    try:
        # Check if we have the new Oauth secrets
        if "oauth" not in st.secrets:
            st.error("❌ Configuration Error: 'oauth' section missing in secrets.toml")
            return None

        oauth_secrets = st.secrets["oauth"]

        # Create Credentials object from Refresh Token
        creds = Credentials(
            None, # No access token initially (it will fetch one)
            refresh_token=oauth_secrets["refresh_token"],
            token_uri="https://oauth2.googleapis.com/token",
            client_id=oauth_secrets["client_id"],
            client_secret=oauth_secrets["client_secret"],
            scopes=SCOPES
        )

        # Force a refresh to check validity
        if not creds.valid:
            creds.refresh(Request())

        # Authorize gspread
        client = gspread.authorize(creds)
        return client

    except Exception as e:
        st.error(f"❌ OAuth Error: {e}")
        return None

def get_or_create_spreadsheet(sheet_name, folder_id=None):
    """
    Finds a sheet by name. If missing, CREATES it using the User's own storage.
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
            # Create sheet (This uses YOUR Drive storage now)
            sh = client.create(sheet_name)
            
            # Optional: Move to specific folder
            if folder_id:
                try:
                    # Using Drive API directly to move file is complex in gspread.
                    # For now, it creates in "My Drive" root.
                    # Detailed move logic would require PyDrive or Google Drive API client.
                    pass 
                except Exception as e:
                    print(f"Folder move warning: {e}")
            
            # Share with others if needed (e.g. your service email if you still used it)
            # But since it's YOUR file, you are already the owner.
            
            return sh.url
        except Exception as e:
            st.error(f"❌ Error creating sheet: {e}")
            return None

def read_data_from_sheet(sheet_url):
    """
    Reads all records from the first tab.
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
        
        # Check headers
        if not worksheet.row_values(1):
            headers = list(data_list[0].keys())
            worksheet.append_row(headers)
            
        # Prepare values
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
    Completely clears and rewrites the sheet (For Edit Mode).
    """
    client = init_google_sheet_client()
    if not client: return False

    try:
        sh = client.open_by_url(sheet_url)
        worksheet = sh.get_worksheet(0)
        
        worksheet.clear()
        df_clean = df.fillna("") 
        data_to_upload = [df_clean.columns.values.tolist()] + df_clean.values.tolist()
        worksheet.update(data_to_upload)
        return True
        
    except Exception as e:
        st.error(f"❌ Save Error: {e}")
        return False
