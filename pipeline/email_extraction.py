"""
pipeline/email_extraction.py
Fetches contacts + emails for a list of domains using the Apollo.io API.
"""

import requests
import time
import os
import csv
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

_MOCK_FILE = Path(__file__).resolve().parent.parent / "data" / "mock_contacts.csv"

API_KEY = os.getenv("APOLLO_API_KEY")

HEADERS = {
    "Content-Type": "application/json",
    "Cache-Control": "no-cache",
    "X-Api-Key": API_KEY,
}


def get_emails_for_company(domain: str, max_people: int = 3) -> list[dict]:
    """
    Query Apollo for up to `max_people` contacts at `domain`.
    If data/mock_contacts.csv exists, uses that instead (for testing).
    Returns a list of dicts with keys: company, title, name, email.
    """
    # ── Mock bypass ───────────────────────────────────────────────────────────
    if _MOCK_FILE.exists():
        with open(_MOCK_FILE, encoding="utf-8") as f:
            rows = [r for r in csv.DictReader(f) if r.get("domain") == domain]
        print(f"  [MOCK] {len(rows)} contact(s) loaded from mock_contacts.csv")
        return rows[:max_people]
    # ─────────────────────────────────────────────────────────────────────────

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
    Run extraction across multiple domains via Apollo.
    Returns real contacts only — no fallback injection.
    If Apollo returns nothing for a domain, that domain is skipped.
    """
    all_contacts: list[dict] = []
    for domain in domains:
        print(f"\n--- Processing {domain} ---")
        contacts = get_emails_for_company(domain, max_people=max_people)
        if contacts:
            all_contacts.extend(contacts)
        else:
            print(f"  Apollo returned no contacts for {domain} — skipping")

    return all_contacts