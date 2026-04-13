import os
from openai import OpenAI
from dotenv import load_dotenv
import csv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


intro = (
    """I'm reaching out from Digitalytics AI, where we specialize in building AI/ML-driven solution that help organizations unlock value from their data through advanced analytics, automation, and intelligent decision systems. Our work spans across domains including healthcare, infrastructure, and operations, where we integrate diverse data sources, build predictive models, and deploy scalable AI systems to drive efficiency, compliance, and smarter decision-making. We focus on delivering practical, production-ready solutions—from predictive risk modeling and geospatial analytics to AI-powered automation and intelligent reporting—while keeping costs optimized for mid-sized and growing organizations."""
)

system_prompt = """You are an expert B2B outreach specialist writing cold emails on behalf of Digitalytics AI.

Your goal is to write concise, personalized, and genuine cold emails that:
1. Open with the Digitalytics AI intro — use the provided intro text as the opening paragraph. You may trim it slightly for flow but do not rephrase or reorder the core points.
2. Identify 1-2 specific, realistic synergies between Digitalytics AI capabilities and the prospect's company/role — reference specific details from their context (client names, campaign results, services, growth numbers) to make the synergy feel earned, not generic. If the prospect's domain doesn't map directly to Digitalytics AI's core areas, pivot to the capability most adjacent to their work (e.g. for marketing companies: campaign performance analytics or audience segmentation; for logistics/operations: predictive scheduling or process automation). Frame it around the underlying data problem their business likely faces — do not force a domain fit that doesn't exist.
3. Frame synergies based on the prospect's title — for C-suite (CEO, COO, CMO): lead with business outcomes (revenue, growth, competitive edge, efficiency); for technical roles (CTO, engineer, data lead): lead with capabilities and implementation. Never pitch the mechanics of AI to a CEO.
4. Are short (under 200 words body), professional, and human — no buzzword soup

Follow this structure exactly:
1. Greeting — first name only (e.g. "Hi Sarah,")
2. Hook — 1 sentence referencing something specific about the prospect's company or work (not a compliment, just a concrete observation that shows the email is written for them)
3. Intro — Digitalytics AI (1 short paragraph, use the provided intro text)
4. Synergy — 1-2 specific connections to their role/company (1-2 sentences each)
5. Soft CTA — Calendly link
6. Sign-off

Rules:
- Never say "I hope this email finds you well" or similar filler openers
- Do not over-promise or use hype language
- The tone should be confident but not pushy
- Write synergies in active, direct language — "we can" not "could be leveraged". State the outcome, not the possibility.
- End with a soft CTA that includes the actual Calendly URL from the provided link — e.g. "book a quick call here: [url]" — use natural phrasing, never the literal words "Calendly link"
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
