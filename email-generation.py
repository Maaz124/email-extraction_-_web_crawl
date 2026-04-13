import os
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
import csv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ── Load Digitalytics capability context ──────────────────────────────────
_CONTEXT_FILE = Path(__file__).resolve().parent / "digit_context.md"
try:
    SENDER_CONTEXT = _CONTEXT_FILE.read_text(encoding="utf-8")
except FileNotFoundError:
    SENDER_CONTEXT = "(digit_context.md not found)"


intro = (
    """I'm reaching out from Digitalytics AI, where we specialize in building AI/ML-driven solution that help organizations unlock value from their data through advanced analytics, automation, and intelligent decision systems. Our work spans across domains including healthcare, infrastructure, and operations, where we integrate diverse data sources, build predictive models, and deploy scalable AI systems to drive efficiency, compliance, and smarter decision-making. We focus on delivering practical, production-ready solutions—from predictive risk modeling and geospatial analytics to AI-powered automation and intelligent reporting—while keeping costs optimized for mid-sized and growing organizations."""
)

system_prompt = f"""You are an expert B2B outreach specialist writing cold emails on behalf of Digitalytics AI.

## Sender Company: Digitalytics AI — Full Capability Reference
Use the following detailed capability document to identify specific, accurate synergies with the prospect's company. Always draw from real capabilities listed here — never invent features.

{SENDER_CONTEXT}

---

## Your Goal
Write a concise, personalized, and genuine cold email that:
1. Opens with the Digitalytics AI intro paragraph (provided in the user prompt) — use it close to verbatim as the opening. You may trim slightly for flow but do not rephrase core points.
2. Identifies 1-2 specific, realistic synergies between Digitalytics capabilities (from the reference above) and the prospect's company/role. Reference specific details from the prospect's context (client names, services, growth stats) to make the synergy feel earned, not generic. If the prospect's domain doesn't map directly, pivot to the most adjacent capability and frame it around the underlying data/automation problem their business likely faces.
3. Frames the synergy based on the prospect's title — C-suite (CEO, COO, CMO): lead with business outcomes (revenue, efficiency, growth); technical roles (CTO, engineer, data lead): lead with capabilities and implementation.
4. Is short (under 200 words body), professional, and human — no buzzword soup.

## Email Structure (follow exactly)
1. Greeting — first name only (e.g. "Hi Sarah,")
2. Hook — 1 sentence referencing something specific about the prospect's company or work (not a compliment — a concrete observation proving the email is written for them)
3. Intro — Digitalytics AI (1 short paragraph, use the provided intro text)
4. Synergy — 1-2 specific connections to their role/company (1-2 sentences each), drawn from the capability reference above
5. Soft CTA — include the actual Calendly URL with natural phrasing (e.g. "book a quick call here: [url]")
6. Sign-off

## Rules
- Never say "I hope this email finds you well" or similar filler
- Do not over-promise or use hype language
- Write synergies in active, direct language — "we can" not "could be leveraged"
- State the outcome, not the possibility
- Never use the literal words "Calendly link" — embed the URL naturally
- Output ONLY the email body (no subject line, no metadata)
"""

def generate_email(name, email, title, content, company_name, sender_name="Digitalytics AI Team"):
    first_name = name.strip().split()[0]
    calendly_link="https://calendar.google.com/calendar/u/0/r"
    user_prompt = f"""Write a cold outreach email for the following prospect:

Name: {name}
Title: {title}
Company: {company_name}
Additional context about them or their company: {content}
Calendly Link: {calendly_link}
Sender Name: {sender_name}

Digitalytics intro (use this as the opening paragraph):
\"\"\"{intro}\"\"\"

Address them as {first_name}. Sign off with the sender's name. The total email body (including intro) must be under 200 words. If over, trim from the synergy section — never cut the intro or the CTA. Output only the email body."""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
    )

    return response.choices[0].message.content.strip()


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
    return response.choices[0].message.content.strip()


if __name__ == "__main__":
    # Load crawled data into a dictionary mapping domain -> content
    crawled_data = {}
    try:
        with open("crawled_output.csv", "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                domain = row.get("domain", "")
                crawled_data[domain] = row.get("scraped_content", "")
    except FileNotFoundError:
        print("crawled_output.csv not found. Please run the pipeline first.")

    # Read emails and generate content
    print("Generating emails based on extracted data...")
    try:
        with open("emails_output.csv", "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                company_domain = row.get("company", "")
                name = row.get("name", "")
                title = row.get("title", "")
                email = row.get("email", "")
                
                # Fetch the corresponding crawled data for this company
                content = crawled_data.get(company_domain, "No additional context available.")
                
                print(f"\n--- Generating email for {name} ({title}) at {company_domain} ---")
                
                try:
                    result = generate_email(
                        name=name,
                        email=email,
                        title=title,
                        content=content,
                        company_name=company_domain
                    )
                    print(result)
                except Exception as e:
                    print(f"Failed to generate email: {e}")
                print("-" * 50)
                
    except FileNotFoundError:
        print("emails_output.csv not found. Please run the pipeline first.")
