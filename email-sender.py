import os
import base64
import importlib.util
from email.mime.text import MIMEText

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

load_dotenv()

# Load email-generation.py (hyphen in filename prevents normal import)
_spec = importlib.util.spec_from_file_location(
    "email_generation",
    os.path.join(os.path.dirname(__file__), "email-generation.py"),
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
generate_email = _mod.generate_email
generate_subject = _mod.generate_subject

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
    import csv

    # 1. Load crawled content
    crawled_data = {}
    if os.path.exists("crawled_output.csv"):
        with open("crawled_output.csv", "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                domain = row.get("domain", "")
                crawled_data[domain] = row.get("scraped_content", "")
    else:
        print("Warning: crawled_output.csv not found.")

    # 2. Setup email service
    try:
        service = get_gmail_service()
    except Exception as e:
        print(f"Failed to initialize Gmail service: {e}")
        exit(1)
    
    # 3. Read emails and send
    if os.path.exists("emails_output.csv"):
        with open("emails_output.csv", "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                company_domain = row.get("company", "")
                name = row.get("name", "")
                title = row.get("title", "")
                email = row.get("email", "")
                
                if not email or email.strip() == "":
                    print(f"\n--- Skipping {name} ({title}) at {company_domain} — No email address found ---")
                    continue
                
                content = crawled_data.get(company_domain, "No additional context available.")
                
                print(f"\n--- Processing {name} ({title}) at {company_domain} ---")
                try:
                    # Generate email body
                    print(f"Drafting generated AI email for {name}...")
                    body = generate_email(
                        name=name,
                        email=email,
                        title=title,
                        content=content,
                        company_name=company_domain,
                    )
                    
                    # AI-generate a specific subject line
                    print(f"Generating subject line for {name}...")
                    subject = generate_subject(body, name, company_domain)
                    print(f"Subject: {subject}")
                    send_email(service, to=email, subject=subject, body=body)
                except Exception as e:
                    print(f"Failed to generate/send email for {email}: {e}")
    else:
        print("Warning: emails_output.csv not found.")
