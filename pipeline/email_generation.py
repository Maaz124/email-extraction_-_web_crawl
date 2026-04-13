"""
pipeline/email_generation.py
Generates personalised cold-outreach emails via OpenAI.
"""

import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

INTRO = (
    "I'm reaching out from Digitalytics AI, where we specialize in building AI/ML-driven "
    "solutions that help organizations unlock value from their data through advanced analytics, "
    "automation, and intelligent decision systems. Our work spans across domains including "
    "healthcare, infrastructure, and operations, where we integrate diverse data sources, build "
    "predictive models, and deploy scalable AI systems to drive efficiency, compliance, and "
    "smarter decision-making. We focus on delivering practical, production-ready solutions—from "
    "predictive risk modeling and geospatial analytics to AI-powered automation and intelligent "
    "reporting—while keeping costs optimized for mid-sized and growing organizations."
)

SYSTEM_PROMPT = """\
You are an expert B2B outreach specialist writing cold emails on behalf of Digitalytics AI.

Your goal is to write concise, personalized, and genuine cold emails that:
1. Open with a brief, natural intro of Digitalytics AI (use the provided intro text, don't paraphrase it heavily)
2. Identify 1-2 specific, realistic synergies between Digitalytics AI capabilities and the prospect's company/role \
— be concrete, not generic. If you can't find a clear synergy from the context given, be honest and focus on the \
most relevant capability rather than making things up.
3. Are short (under 200 words body), professional, and human — no buzzword soup

Rules:
- Never say "I hope this email finds you well" or similar filler openers
- Do not over-promise or use hype language
- The tone should be confident but not pushy
- Address the person by first name only
- End with a soft CTA pointing to the Calendly link
- Output ONLY the email body (no subject line, no metadata)
"""

CALENDLY_LINK = "https://calendar.google.com/calendar/u/0/r"


def generate_email(name: str, email: str, title: str, content: str, company_name: str) -> str:
    """Return the generated email body as a string."""
    first_name = name.strip().split()[0]
    user_prompt = f"""\
Write a cold outreach email for the following prospect:

Name: {name}
Title: {title}
Company: {company_name}
Additional context about them or their company: {content}
Calendly Link: {CALENDLY_LINK}

Use this Digitalytics intro (keep it close to verbatim, it can be slightly trimmed):
\"\"\"{INTRO}\"\"\"

Address them as {first_name}. Output only the email body."""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()


def generate_subject(company_name: str) -> str:
    return f"AI / ML Synergies for {company_name.capitalize()}"
