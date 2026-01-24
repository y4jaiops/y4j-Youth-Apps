# (Database Access) Handles saving data to the y4jAiOps Google Drive Sheets.

import streamlit as st
import gspread
from googleapiclient.discovery import build
from logic.logic_drive import _get_admin_creds

def _get_client():
    creds = _get_admin_creds()
    if not creds: return None
    return gspread.authorize(creds)

def get_or_create_spreadsheet(filename, folder_id=None):
    client = _get_client()
    if not client: return None
    try:
        return client.open(filename).url
    except gspread.SpreadsheetNotFound:
        try:
            creds = _get_admin_creds()
            service = build('drive', 'v3', credentials=creds)
            metadata = {'name': filename, 'mimeType': 'application/vnd.google-apps.spreadsheet'}
            if folder_id: metadata['parents'] = [folder_id]
            file = service.files().create(body=metadata, fields='id').execute()
            return client.open_by_key(file.get('id')).url
        except Exception as e:
            st.error(f"Create Error: {e}")
            return None

def append_batch_to_sheet(sheet_url, list_of_dicts):
    if not list_of_dicts: return True
    try:
        client = _get_client()
        sheet = client.open_by_url(sheet_url).sheet1
        existing = sheet.row_values(1)
        headers = existing if existing else list(list_of_dicts[0].keys())
        if not existing: sheet.append_row(headers)
        rows = [[d.get(h, "") for h in headers] for d in list_of_dicts]
        sheet.append_rows(rows)
        return True
    except Exception as e:
        st.error(f"Save Error: {e}")
        return False
