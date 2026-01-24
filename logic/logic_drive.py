# (Storage Access) Handles downloading resumes/JDs from the y4jAiOps google Drive.
import streamlit as st
import io
import re
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

def _get_admin_creds():
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
    match = re.search(r'id=([a-zA-Z0-9_-]+)', drive_link) or re.search(r'/d/([a-zA-Z0-9_-]+)', drive_link)
    file_id = match.group(1) if match else (drive_link if len(drive_link) > 20 else None)
    
    if not file_id: return None, None, "Invalid Link"
    creds = _get_admin_creds()
    if not creds: return None, None, "Auth Failed"

    try:
        service = build('drive', 'v3', credentials=creds)
        meta = service.files().get(fileId=file_id, fields="name, mimeType").execute()
        request = service.files().get_media(fileId=file_id)
        file_io = io.BytesIO()
        downloader = MediaIoBaseDownload(file_io, request)
        done = False
        while not done: _, done = downloader.next_chunk()
        return file_io.getvalue(), meta.get('mimeType'), None
    except Exception as e:
        return None, None, str(e)
