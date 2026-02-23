import streamlit as st
import gspread
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# --- CONFIGURATION ---
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

class Y4JGoogleClient:
    """
    A wrapper class that combines gspread for spreadsheet manipulation 
    and the Google Drive API for advanced file querying.
    """
    def __init__(self, creds):
        # Initialize gspread client
        self.gspread_client = gspread.authorize(creds)
        # Initialize Google Drive v3 API client
        self.drive_service = build('drive', 'v3', credentials=creds)

    # --- Drive API Methods ---
    def list_files_by_query(self, query):
        """
        Executes a custom query against the Google Drive API.
        Returns a list of file dictionaries containing 'id' and 'name'.
        """
        results = self.drive_service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name)',
            pageSize=1000
        ).execute()
        
        return results.get('files', [])

    # --- Gspread Pass-Through Methods ---
    def open_by_key(self, file_id):
        return self.gspread_client.open_by_key(file_id)

    def open(self, title, folder_id=None):
        if folder_id:
            return self.gspread_client.open(title, folder_id=folder_id)
        return self.gspread_client.open(title)

    def create(self, title, folder_id=None):
        if folder_id:
            return self.gspread_client.create(title, folder_id=folder_id)
        return self.gspread_client.create(title)

    def open_by_url(self, url):
        return self.gspread_client.open_by_url(url)

@st.cache_resource(show_spinner="Connecting to Google Workspace...")
def init_google_sheet_client():
    """
    Authenticate using OAuth 2.0 Refresh Token (Acts as the User, not a Service Account).
    This bypasses Service Account storage quotas and returns a unified client
    for both Sheets and Drive API operations.
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

        # Return the wrapper client containing both gspread and drive APIs
        return Y4JGoogleClient(creds)

    except Exception as e:
        st.error(f"❌ OAuth Error: {e}")
        return None

def get_or_create_spreadsheet(sheet_name, folder_id=None):
    """
    Finds a sheet by name. If missing, CREATES it using the User's own storage.
    If folder_id is provided, the sheet is created directly inside that specific folder.
    """
    client = init_google_sheet_client()
    if not client: return None

    try:
        # 1. Try to open existing sheet
        # We also pass folder_id here so it strictly opens files in the Y4J folder
        sh = client.open(sheet_name, folder_id=folder_id)
        return sh.url
        
    except gspread.SpreadsheetNotFound:
        # 2. Create new if not found
        try:
            # THE FIX: Create the sheet directly in the target folder
            sh = client.create(sheet_name, folder_id=folder_id)
            
            # (Optional) You can automatically share this new sheet with an admin 
            # by un-commenting the line below and adding an admin email:
            # sh.gspread_client.share('admin_email@example.com', perm_type='user', role='writer')
            
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
    Safely handles Pandas/Numpy data types before uploading to Google Sheets.
    """
    client = init_google_sheet_client()
    if not client: return False

    try:
        sh = client.open_by_url(sheet_url)
        worksheet = sh.get_worksheet(0)
        
        worksheet.clear()
        
        # 1. Create a copy to avoid SettingWithCopyWarning
        df_clean = df.copy()
        
        # 2. Fill NA/NaN values with empty strings
        df_clean = df_clean.fillna("")
        
        # 3. Convert all columns to strings to avoid numpy JSON serialization errors
        # (Google Sheets will automatically auto-detect numbers and dates upon insertion)
        df_clean = df_clean.astype(str)
        
        # 4. Prepare data for upload
        data_to_upload = [df_clean.columns.values.tolist()] + df_clean.values.tolist()
        
        # 5. Update the sheet
        worksheet.update(data_to_upload)
        return True
        
    except Exception as e:
        st.error(f"❌ Save Error: {e}")
        return False

