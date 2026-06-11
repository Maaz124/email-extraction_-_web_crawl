"""
Run this ONCE to authorize the second Gmail sending account.
It will open a browser window — sign in with the SECOND Gmail account.
Saves credentials to token2.json in the project root.

Usage:
    python build-token2.py
"""
import os
import json
from pathlib import Path
from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
TOKEN_FILE = Path(__file__).resolve().parent / "token2.json"

client_config = {
    "installed": {
        "client_id":     os.environ["CLIENT_ID"],
        "client_secret": os.environ["CLIENT_SECRET"],
        "auth_uri":      "https://accounts.google.com/o/oauth2/auth",
        "token_uri":     "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"],
    }
}

print("Opening browser — sign in with your SECOND Gmail account...")
flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
creds = flow.run_local_server(port=0)

TOKEN_FILE.write_text(creds.to_json())
print(f"token2.json saved to: {TOKEN_FILE}")
print("Second account is ready.")
