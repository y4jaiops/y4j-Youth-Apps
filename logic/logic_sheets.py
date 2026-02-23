import streamlit as st
import gspread
import time
import random
from functools import wraps
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# --- CONFIGURATION ---
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# --- EXPONENTIAL BACKOFF DECORATOR ---
def with_exponential_backoff(max_retries=5, base_delay=2):
    """
    Catches Google API 429 Quota errors and automatically retries the function
    with an increasing delay to allow the quota to reset.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    error_msg = str(e).lower()
                    if "429" in error_msg or "quota" in error_msg:
                        if attempt < max_retries - 1:
                            # Calculate exponential wait time with jitter
                            sleep_time = (base_delay ** attempt) + random.uniform(0, 1)
                            st.toast(f"⏳ API cooling down for {sleep_time:.1f}s (Attempt {attempt+1}/{max_retries})...")
                            time.sleep(sleep_time)
                        else:
                            st.error(f"❌ Max retries reached: {e}")
                            raise e
                    else:
                        raise e
        return wrapper
    return decorator


class Y4JGoogleClient:
    """
    A wrapper class that combines gspread for spreadsheet manipulation 
    and the Google Drive API for advanced file querying and moving.
    """
    def __init__(self, creds):
        self.gspread_client = gspread.authorize(creds)
        self.drive_service = build('drive', 'v3', credentials=creds)

    def list_files_by_query(self, query):
        """Fetches files matching a specific Drive query."""
        results = self.drive_service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name)',
            pageSize=1000,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        return results.get('files', [])

    def get_file_id_by_name(self, title, folder_id=None):
        """Safely queries Drive to find the exact file inside the target folder."""
        query = f"name='{title}' and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false"
        if folder_id:
            query += f" and '{folder_id}' in parents"
            
        results = self.drive_service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name)',
            supportsAllDrives=True, 
            includeItemsFromAllDrives=True
        ).execute()
        
        files = results.get('files', [])
        return files[0]['id'] if files else None

    def open(self, title, folder_id=None):
        """Finds the specific ID using Drive API, then opens it with gspread."""
        file_id = self.get_file_id_by_name(title, folder_id)
        if file_id:
            return self.gspread_client.open_by_key(file_id)
        raise gspread.SpreadsheetNotFound(f"Spreadsheet '{title}' not found in folder.")
        
    def open_by_key(self, file_id):
        """Opens a spreadsheet directly using its Drive file ID."""
        return self.gspread_client.open_by_key(file_id)

    def create(self, title, folder_id=None):
        """Creates the sheet and explicitly forces it into the target folder."""
        sh = self.gspread_client.create(title)
        
        if folder_id:
            file_id = sh.id
            try:
                file = self.drive_service.files().get(
                    fileId=file_id, 
                    fields='parents',
                    supportsAllDrives=True
                ).execute()
                previous_parents = ",".join(file.get('parents', []))
                
                self.drive_service.files().update(
                    fileId=file_id,
                    addParents=folder_id,
                    removeParents=previous_parents,
                    fields='id, parents',
                    supportsAllDrives=True
                ).execute()
            except Exception as e:
                st.warning(f"File created, but encountered an error moving it to the folder: {e}")
        
        return sh

    def open_by_url(self, url):
        return self.gspread_client.open_by_url(url)



@st.cache_resource(show_spinner="Connecting to Google Workspace...")
def init_google_sheet_client():
    try:
        if "oauth" not in st.secrets:
            st.error("❌ Configuration Error: 'oauth' section missing in secrets.toml")
            return None

        oauth_secrets = st.secrets["oauth"]

        creds = Credentials(
            None, 
            refresh_token=oauth_secrets["refresh_token"],
            token_uri="https://oauth2.googleapis.com/token",
            client_id=oauth_secrets["client_id"],
            client_secret=oauth_secrets["client_secret"],
            scopes=SCOPES
        )

        if not creds.valid:
            creds.refresh(Request())

        return Y4JGoogleClient(creds)

    except Exception as e:
        st.error(f"❌ OAuth Error: {e}")
        return None

def get_or_create_spreadsheet(sheet_name, folder_id=None):
    client = init_google_sheet_client()
    if not client: return None

    try:
        # Now uses our bulletproof Drive API search
        sh = client.open(sheet_name, folder_id=folder_id)
        return sh.url
    except gspread.SpreadsheetNotFound:
        try:
            # Now uses our bulletproof Drive API move command
            sh = client.create(sheet_name, folder_id=folder_id)
            return sh.url
        except Exception as e:
            st.error(f"❌ Error creating sheet: {e}")
            return None

def read_data_from_sheet(sheet_url):
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
    if not data_list: return True
    
    client = init_google_sheet_client()
    if not client: return False

    try:
        sh = client.open_by_url(sheet_url)
        worksheet = sh.get_worksheet(0)
        
        if not worksheet.row_values(1):
            headers = list(data_list[0].keys())
            worksheet.append_row(headers)
            
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

@with_exponential_backoff(max_retries=5)
def overwrite_sheet_with_df(sheet_url, df):
    """
    Completely clears and rewrites the sheet (For Edit Mode).
    Safely handles Pandas/Numpy data types before uploading to Google Sheets.
    """
    client = init_google_sheet_client()
    if not client: return False

    sh = client.open_by_url(sheet_url)
    worksheet = sh.get_worksheet(0)
    
    worksheet.clear()
    
    df_clean = df.copy()
    df_clean = df_clean.fillna("")
    df_clean = df_clean.astype(str)
    
    data_to_upload = [df_clean.columns.values.tolist()] + df_clean.values.tolist()
    worksheet.update(data_to_upload)
    return True
