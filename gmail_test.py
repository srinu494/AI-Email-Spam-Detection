import os
import base64
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_FILE = os.path.join(BASE_DIR, "credentials_new.json")
TOKEN_FILE = os.path.join(BASE_DIR, "token.json")


def clear_saved_token():
    """Remove this app's locally saved OAuth token; does not delete Gmail data."""
    if os.path.exists(TOKEN_FILE):
        os.remove(TOKEN_FILE)


def connect_gmail(force_account_selection=True):
    if not os.path.exists(CREDENTIALS_FILE):
        raise FileNotFoundError("credentials_new.json file is missing from python-api folder.")

    # Do not silently reuse the previous account's token. Ask Google to show
    # its account chooser for every new login.
    if force_account_selection:
        clear_saved_token()
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
        credentials = flow.run_local_server(port=0, prompt="select_account")
        with open(TOKEN_FILE, "w", encoding="utf-8") as token_file:
            token_file.write(credentials.to_json())
    else:
        credentials = None
        if os.path.exists(TOKEN_FILE):
            credentials = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                credentials = flow.run_local_server(port=0, prompt="select_account")
            with open(TOKEN_FILE, "w", encoding="utf-8") as token_file:
                token_file.write(credentials.to_json())

    return build("gmail", "v1", credentials=credentials)


def decode_email_body(payload):
    mime_type = payload.get("mimeType", "")
    if mime_type == "text/plain":
        body_data = payload.get("body", {}).get("data")
        if body_data:
            decoded_bytes = base64.urlsafe_b64decode(body_data)
            return decoded_bytes.decode("utf-8", errors="replace")
    body_text = ""
    for part in payload.get("parts", []):
        body_text += decode_email_body(part)
    return body_text


def get_header(headers, header_name):
    for header in headers:
        if header.get("name", "").lower() == header_name.lower():
            return header.get("value", "")
    return ""
