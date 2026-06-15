"""
Create token2.json for the second Gmail sending account.

Default usage:
    python build-token2.py

The script asks for a refresh token and writes token2.json in the project root.
You can also set GMAIL_ACCOUNT2_REFRESH_TOKEN to avoid the prompt.

Local desktop OAuth, if a browser is available:
    python build-token2.py --browser
"""
import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
TOKEN_FILE = Path(__file__).resolve().parent / "token2.json"


def client_config() -> dict:
    return {
        "installed": {
            "client_id": os.environ["CLIENT_ID"],
            "client_secret": os.environ["CLIENT_SECRET"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }


def write_from_refresh_token(refresh_token: str) -> None:
    token_data = {
        "token": None,
        "refresh_token": refresh_token.strip(),
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": os.environ["CLIENT_ID"],
        "client_secret": os.environ["CLIENT_SECRET"],
        "scopes": SCOPES,
        "expiry": None,
    }
    TOKEN_FILE.write_text(json.dumps(token_data, indent=2))


def write_from_browser_oauth() -> None:
    print("Opening browser — sign in with the SECOND Gmail account...")
    flow = InstalledAppFlow.from_client_config(client_config(), SCOPES)
    creds = flow.run_local_server(port=0)
    TOKEN_FILE.write_text(creds.to_json())


def main() -> None:
    parser = argparse.ArgumentParser(description="Create token2.json for Gmail Account 2.")
    parser.add_argument(
        "--browser",
        action="store_true",
        help="Run browser-based OAuth locally instead of using a pasted refresh token.",
    )
    args = parser.parse_args()

    if args.browser:
        write_from_browser_oauth()
    else:
        refresh_token = os.getenv("GMAIL_ACCOUNT2_REFRESH_TOKEN")
        if not refresh_token:
            refresh_token = input("Paste refresh token for the SECOND Gmail account: ").strip()
        if not refresh_token:
            raise SystemExit("No refresh token provided; token2.json was not created.")
        write_from_refresh_token(refresh_token)

    print(f"token2.json saved to: {TOKEN_FILE}")
    print("Second account is ready.")


if __name__ == "__main__":
    main()
