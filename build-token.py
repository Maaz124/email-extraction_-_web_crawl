"""
Run this once after getting the refresh_token from Google OAuth Playground.
Paste the refresh_token below and run — it creates token.json locally.
"""
import json
import os
from dotenv import load_dotenv

load_dotenv()

REFRESH_TOKEN = "1//04RN45M4VDYYmCgYIARAAGAQSNwF-L9Irjdkx4nfEqTdUEv9zQ8JrkrXYpiP4kG0Tg8oiuKcCY1aJxJ_PL-QOOfvof5CWhz0TPhA"

token_data = {
    "token": None,
    "refresh_token": REFRESH_TOKEN,
    "token_uri": "https://oauth2.googleapis.com/token",
    "client_id": os.environ["CLIENT_ID"],
    "client_secret": os.environ["CLIENT_SECRET"],
    "scopes": ["https://www.googleapis.com/auth/gmail.send"],
    "expiry": None,
}

with open("token.json", "w") as f:
    json.dump(token_data, f, indent=2)

print("token.json created successfully.")
