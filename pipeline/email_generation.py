"""
pipeline/email_generation.py
Generates personalised cold-outreach emails via OpenAI.
"""

import os
import re
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
from pipeline.log import logger

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ── Load Digitalytics capability context from digit_context.md ────────────────
_CONTEXT_FILE = Path(__file__).resolve().parent.parent / "digit_context.md"
try:
    SENDER_CONTEXT = _CONTEXT_FILE.read_text(encoding="utf-8")
except FileNotFoundError:
    SENDER_CONTEXT = "(No additional sender context found — digit_context.md missing)"

INTRO = (
    "At Digitalytics AI, we work with independent medical practices to reduce the "
    "administrative workload that consumes staff time and leads to delays, errors, "
    "and operational bottlenecks."
)

PAIN_POINTS = """\
- Staff spending valuable hours on repetitive data entry and paperwork
- Incoming referrals and lab results requiring manual processing
- Missed or delayed patient calls during busy periods or after hours
- Front-desk teams juggling scheduling, intake, and follow-up tasks simultaneously
- Administrative errors that can impact billing, documentation, and patient experience"""

SOLUTIONS = """\
- Patient call handling, appointment scheduling, rescheduling, and refill requests
- Referral and lab-result processing directly into the EHR
- Digital patient intake and registration workflows
- Appointment reminders, follow-ups, and patient outreach programs"""

SYSTEM_PROMPT = f"""\
You are writing a cold outreach email on behalf of Digitalytics AI, targeting independent medical practices.

## Email Structure (follow exactly, in this order)
1. Greeting — use the exact greeting string provided in the user message. Do not modify it.
2. One warm opener sentence — brief and genuine. Do NOT use "I hope this email finds you well", "I came across your website", or any similar filler.
3. Intro sentence — use the INTRO text close to verbatim: "{INTRO}"
4. Pain points intro line (e.g. "Many practices we speak with are navigating challenges like:") followed by this exact bullet list:
{PAIN_POINTS}
5. Solutions intro line (e.g. "To address this, we've built AI-driven workflows that handle:") followed by this exact bullet list:
{SOLUTIONS}
6. Value prop sentence (use verbatim): "The goal isn't simply automation — it is helping clinics operate more efficiently, reducing administrative burden, improving accuracy, and allowing staff to focus more on patient care."
7. Personalized closing (1-2 sentences): Reference something specific from the crawled website data about this practice — their specialty, patient focus, size, services, or stated goals. If the crawled data is sparse, pivot to a genuine observation about the challenges their specialty typically faces. Make it feel written for them specifically.
8. Video demo offer (use verbatim): "We've also put together a short video demonstration that shows several of these workflows in action. If you'd like, I'd be happy to send it over for a quick look."
9. Discovery close (use verbatim): "If any of these challenges sound familiar, I'd welcome the opportunity to learn more about your practice."
10. Sign-off: "Best regards," — nothing after this line.

## Rules
- Do NOT include any Calendly URL or link anywhere in the body
- Do NOT add any name, title, or website after "Best regards," — the HTML footer handles this
- Do NOT paraphrase, reorder, or omit any bullet items from the pain points or solutions lists
- Do NOT use filler openers ("I hope you're doing well", "I came across your website")
- Keep the total body under 220 words
- Output ONLY the email body (no subject line, no metadata)
"""


def generate_email(
    name: str,
    email: str,
    title: str,
    content: str,
    company_name: str,
    sender_name: str = "Digitalytics AI Team",
    greeting: str = "",
) -> str:
    """Return the AI-generated email body as a string."""
    first_name = name.strip().split()[0]
    resolved_greeting = greeting if greeting else f"Hi Dr. {first_name},"
    user_prompt = f"""\
Write a clinic-targeted cold outreach email for the following prospect:

Name: {name}
Title: {title}
Practice / Company: {company_name}
Crawled website context (use for the personalized closing paragraph): {content}

Follow the email structure from the system prompt exactly.
Use this exact greeting: "{resolved_greeting}"
End the email with "Best regards," and nothing else after it.
Total body must be under 220 words.
Output only the email body."""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
    )
    usage = response.usage
    logger.info(
        f"[EMAIL BODY] {name} @ {company_name} — "
        f"input tokens: {usage.prompt_tokens}, "
        f"output tokens: {usage.completion_tokens}, "
        f"total: {usage.total_tokens}"
    )
    body = response.choices[0].message.content.strip()
    body = re.sub(r'(?i)(best regards,).*', r'\1', body, flags=re.DOTALL).strip()
    return body


def generate_subject(body: str, name: str, company_name: str) -> str:
    """AI-generate a punchy, specific subject line from the email body."""
    response = client.chat.completions.create(
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
    usage = response.usage
    logger.info(
        f"[SUBJECT LINE] {name} @ {company_name} — "
        f"input tokens: {usage.prompt_tokens}, "
        f"output tokens: {usage.completion_tokens}, "
        f"total: {usage.total_tokens}"
    )
    return response.choices[0].message.content.strip()
