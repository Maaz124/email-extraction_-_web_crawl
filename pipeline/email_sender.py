"""
pipeline/email_sender.py
Handles Gmail OAuth authentication and sending via the Gmail API.
"""

import os
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from pathlib import Path

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

# Default token location: project root (one level above this file)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TOKEN_FILE = str(_PROJECT_ROOT / "token.json")

SENDER_PROFILES = {
    "account1": {
        "from_header":  "Ahsan Ahmad <ahsan.ahmad@digitalytics.ai>",
        "display_name": "Ahsan Ahmad",
        "title":        "Founder, Digitalytics AI",
        "calendly":     "https://calendly.com/ahsan-ahmad-digitalytics/30min",
    },
    "account2": {
        "from_header":  "Abdullah Asif <abdullah.asif@digitalytics.ai>",
        "display_name": "Abdullah Asif",
        "title":        "CTO, Digitalytics AI",
        "calendly":     "https://calendly.com/ahsan-ahmad-digitalytics/30min",
    },
}


def _client_config() -> dict:
    return {
        "installed": {
            "client_id": os.environ["CLIENT_ID"],
            "client_secret": os.environ["CLIENT_SECRET"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }


def get_gmail_service(token_file: str = DEFAULT_TOKEN_FILE):
    """Build and return an authenticated Gmail service object."""
    creds = None

    if os.path.exists(token_file):
        # Load without enforcing scopes — avoids invalid_scope on refresh
        # when token was originally granted with a different scope string.
        creds = Credentials.from_authorized_user_file(token_file)

    if not creds or not creds.token:
        if creds and creds.refresh_token:
            creds._scopes = None  # don't send scope in refresh request
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_config(_client_config(), SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_file, "w") as f:
            f.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def _to_html(plain: str, sender_key: str = "account1") -> str:
    """Convert plain-text email body to a professional branded HTML email."""
    import html as _html
    profile = SENDER_PROFILES[sender_key]

    # ── Convert body paragraphs ───────────────────────────────────────────────
    escaped = _html.escape(plain)
    paragraphs = [p.strip() for p in escaped.split("\n\n") if p.strip()]
    body_html = "".join(
        f"<p style='margin:0 0 16px 0;'>{p.replace(chr(10), '<br>')}</p>"
        for p in paragraphs
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f4f6f8;font-family:Arial,Helvetica,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6f8;padding:32px 0;">
    <tr><td align="center">
      <table width="620" cellpadding="0" cellspacing="0"
             style="background:#ffffff;border-radius:8px;overflow:hidden;
                    box-shadow:0 2px 8px rgba(0,0,0,0.08);max-width:620px;width:100%;">

        <!-- Body -->
        <tr>
          <td style="padding:36px 36px 24px 36px;color:#333333;font-size:15px;line-height:1.7;">
            {body_html}
          </td>
        </tr>

        <!-- CTA Button — right after body -->
        <tr>
          <td style="padding:0 36px 32px 36px;">
            <a href="{profile['calendly']}"
               style="display:inline-block;background:#1a7a5e;color:#ffffff;
                      text-decoration:none;font-size:14px;font-weight:600;
                      padding:12px 24px;border-radius:6px;">
              Book a 30-min Call →
            </a>
          </td>
        </tr>

        <!-- Divider -->
        <tr>
          <td style="padding:0 36px;">
            <hr style="border:none;border-top:1px solid #e8ecef;margin:0;">
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""




def send_email(
    service,
    to: str,
    subject: str,
    body: str,
    attachment_bytes: bytes | None = None,
    attachment_name: str = "portfolio.pdf",
    sender_key: str = "account1",
) -> str:
    """
    Send an HTML-formatted email via the Gmail API.
    Optionally attaches a PDF when attachment_bytes is provided.
    Returns the sent message ID.
    """
    profile = SENDER_PROFILES[sender_key]
    body = body.rstrip() + f"\n\n{profile['display_name']}\n{profile['title']}\nhttps://www.digitalytics.ai"
    html_body = _to_html(body, sender_key=sender_key)

    if attachment_bytes:
        message = MIMEMultipart()
        message.attach(MIMEText(html_body, "html"))
        pdf_part = MIMEApplication(attachment_bytes, _subtype="pdf")
        pdf_part.add_header("Content-Disposition", "attachment", filename=attachment_name)
        message.attach(pdf_part)
    else:
        message = MIMEText(html_body, "html")

    message["to"] = to
    message["from"] = profile["from_header"]
    message["subject"] = subject

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    result = service.users().messages().send(userId="me", body={"raw": raw}).execute()
    label = "Acct1/Ahsan" if sender_key == "account1" else "Acct2/Abdullah"
    print(f"  [{label}] Sent to {to} — Message ID: {result['id']}")
    return result["id"]

