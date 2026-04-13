"""
pipeline/email_extraction.py
Fetches contacts + emails for a list of domains using the Apollo.io API.
"""

import requests
import time
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("APOLLO_API_KEY")

HEADERS = {
    "Content-Type": "application/json",
    "Cache-Control": "no-cache",
    "X-Api-Key": API_KEY,
}


def get_emails_for_company(domain: str, max_people: int = 3) -> list[dict]:
    """
    Query Apollo for up to `max_people` contacts at `domain`.
    Returns a list of dicts with keys: company, title, name, email.
    """
    search_url = "https://api.apollo.io/v1/mixed_people/api_search"
    search_payload = {"q_organization_domains": domain, "page": 1}

    response = requests.post(search_url, json=search_payload, headers=HEADERS)
    people = response.json().get("people", [])

    extracted: list[dict] = []
    for person in people[:max_people]:
        p_id = person.get("id")
        display_name = f"{person.get('first_name')} {person.get('last_name_obfuscated')}"
        print(f"  Fetching email for: {display_name} at {domain}…")

        match_res = requests.post(
            "https://api.apollo.io/v1/people/match",
            json={"id": p_id},
            headers=HEADERS,
        )
        if match_res.status_code == 200:
            full = match_res.json().get("person", {})
            email = full.get("email")
            if email and email.strip():
                extracted.append(
                    {
                        "company": domain,
                        "title": full.get("title", ""),
                        "name": f"{full.get('first_name')} {full.get('last_name')}",
                        "email": email,
                    }
                )
        time.sleep(1)  # rate-limit safety

    return extracted


def extract_contacts(domains: list[str], max_people: int = 3) -> list[dict]:
    """
    Run extraction across multiple domains.
    Injects a test contact if Apollo returns nothing.
    """
    all_contacts: list[dict] = []
    for domain in domains:
        print(f"\n--- Processing {domain} ---")
        contacts = get_emails_for_company(domain, max_people=max_people)
        all_contacts.extend(contacts)

    if not all_contacts:
        print("\n[TEST MODE] Apollo returned 0 valid emails. Injecting test contact…")
        all_contacts.append(
            {
                "company": domains[0] if domains else "digitalytics.ai",
                "title": "CEO",
                "name": "Ahmad Ahsan",
                "email": "ahmadahsan1997@gmail.com",
            }
        )

    return all_contacts