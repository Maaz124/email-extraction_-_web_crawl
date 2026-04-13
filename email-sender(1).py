import os
import base64
import importlib.util
from email.mime.text import MIMEText

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from openai import OpenAI

load_dotenv()

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def generate_subject(body: str, name: str, company_name: str) -> str:
    response = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": (
                    "You write cold email subject lines. "
                    "Rules: under 8 words, specific to the prospect, curiosity-driven but not clickbait. "
                    "Do not use 'Quick question', 'Following up', or generic phrases. "
                    "Output only the subject line — no quotes, no punctuation at the end."
                ),
            },
            {
                "role": "user",
                "content": f"Write a subject line for this cold email sent to {name} at {company_name}:\n\n{body}",
            },
        ],
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()


# Load email-generation.py (hyphen in filename prevents normal import)
_spec = importlib.util.spec_from_file_location(
    "email_generation",
    os.path.join(os.path.dirname(__file__), "email-generation.py"),
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
generate_email = _mod.generate_email

# Only send emails — no reading/deleting
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

TOKEN_FILE = "token.json"

CLIENT_CONFIG = {
    "installed": {
        "client_id": os.environ["CLIENT_ID"],
        "client_secret": os.environ["CLIENT_SECRET"],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"],
    }
}


def get_gmail_service():
    creds = None

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_config(CLIENT_CONFIG, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def send_email(service, to: str, subject: str, body: str, sender: str = "me"):
    message = MIMEText(body)
    message["to"] = to
    message["from"] = sender
    message["subject"] = subject

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    result = service.users().messages().send(userId="me", body={"raw": raw}).execute()
    print(f"Email sent to {to} — Message ID: {result['id']}")
    return result


if __name__ == "__main__":
    recipient_name = "Ahsan Ahmad"
    recipient_email = "ahmadahsan1997@gmail.com"
    recipient_title = "CEO"
    company_name = "33agency"
    content = "Social media marketing agency based in Houston."

    body = generate_email(
        name=recipient_name,
        email=recipient_email,
        title=recipient_title,
        content=content,
        company_name=company_name,
    )

    subject = generate_subject(body, recipient_name, company_name)
    print(f"Generated subject: {subject}")

    service = get_gmail_service()
    send_email(service, to=recipient_email, subject=subject, body=body)

