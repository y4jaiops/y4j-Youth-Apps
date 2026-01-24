# (Storage Access) Handles downloading resumes/JDs from the y4jAiOps google Drive.
import streamlit as st
import io
import re
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

def _get_admin_creds():
    """Uses the Shared Refresh Token to act as the 2TB Admin."""
    if "google_auth" not in st.secrets: return None
    auth = st.secrets["google_auth"]
    creds = Credentials(
        token=None,
        refresh_token=auth["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=auth["client_id"],
        client_secret=auth["client_secret"]
    )
    if not creds.valid: creds.refresh(Request())
    return creds

def get_file_from_link(drive_link):
    """
    Downloads file bytes from Drive Link. 
    Handles Folder detection to prevent 404 errors.
    """
    # 1. CHECK FOR FOLDERS (User Error)
    if "/folders/" in drive_link:
        return None, None, "❌ You pasted a Folder link. Please paste a link to a specific File (PDF or Image)."

    # 2. EXTRACT ID (Improved Regex)
    # Matches: /d/XYZ, id=XYZ, or /file/d/XYZ
    patterns = [
        r'/d/([a-zA-Z0-9_-]+)',
        r'id=([a-zA-Z0-9_-]+)',
        r'/file/d/([a-zA-Z0-9_-]+)'
    ]
    
    file_id = None
    for p in patterns:
        match = re.search(p, drive_link)
        if match:
            file_id = match.group(1)
            break
            
    if not file_id:
        # Fallback: If string is pure ID (no slashes)
        if len(drive_link) > 20 and "/" not in drive_link:
            file_id = drive_link
        else:
            return None, None, "❌ Invalid Google Drive Link. Could not find File ID."

    # 3. DOWNLOAD
    creds = _get_admin_creds()
    if not creds: return None, None, "Auth Failed: Check secrets.toml"

    try:
        service = build('drive', 'v3', credentials=creds)
        
        # Get Metadata
        meta = service.files().get(fileId=file_id, fields="name, mimeType").execute()
        mime_type = meta.get('mimeType')
        
        # Check if it's a native Google Doc/Sheet (cannot download directly)
        if "application/vnd.google-apps" in mime_type:
             return None, None, "❌ Cannot scan native Google Docs/Sheets. Please link a PDF or Image."

        # Download Content
        request = service.files().get_media(fileId=file_id)
        file_io = io.BytesIO()
        downloader = MediaIoBaseDownload(file_io, request)
        
        done = False
        while not done:
            status, done = downloader.next_chunk()
            
        return file_io.getvalue(), mime_type, None

    except Exception as e:
        # Catch 404s cleanly
        if "404" in str(e):
             return None, None, "❌ File not found. Check permissions (Share with y4jaiops@gmail.com)."
        return None, None, f"Drive Error: {str(e)}"
