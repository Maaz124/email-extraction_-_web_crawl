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
    "Cache-Control": "no-cache",
    "Content-Type": "application/json",
    "accept": "application/json",
    "x-api-key": API_KEY,
}

# Title filters — only target decision-makers
TITLE_FILTERS = ["founder", "ceo", "cto", "cmo", "president", "director", "manager"]


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

    # STEP 1: Search by domain + title filters
    params = "&".join(
        [f"person_titles[]={t}" for t in TITLE_FILTERS] +
        [f"q_organization_domains_list[]={domain}"]
    )
    search_url = f"https://api.apollo.io/api/v1/mixed_people/api_search?{params}"

    response = requests.post(search_url, headers=HEADERS)
    if response.status_code != 200:
        print(f"  ⚠️  Apollo search HTTP {response.status_code}: {response.text[:200]}")
        return []

    resp_json  = response.json()
    people     = resp_json.get("people", [])
    total      = resp_json.get("total_entries", 0)
    print(f"  Apollo found {len(people)} people (total indexed: {total})")

    if not people:
        print(f"  ℹ️  No people indexed on Apollo for {domain}")
        return []

    # Only reveal emails for records that claim to have one
    candidates = [p for p in people if p.get("has_email")][:max_people]
    print(f"  {len(candidates)} with email — revealing…")

    extracted: list[dict] = []

    # STEP 2: Reveal each email via people/match
    for person in candidates:
        p_id        = person.get("id")
        display     = f"{person.get('first_name')} {person.get('last_name_obfuscated')}"
        print(f"  Fetching email for: {display} at {domain}…")

        match_res = requests.post(
            "https://api.apollo.io/api/v1/people/match",
            json={"id": p_id},
            headers=HEADERS,
        )

        if match_res.status_code != 200:
            print(f"    ⚠️  Match HTTP {match_res.status_code} for {display}")
            time.sleep(1)
            continue

        full  = match_res.json().get("person", {})
        email = full.get("email")

        if email and email.strip():
            print(f"    ✓ {email}")
            extracted.append({
                "company": domain,
                "title":   full.get("title", ""),
                "name":    f"{full.get('first_name')} {full.get('last_name')}",
                "email":   email,
            })
        else:
            print(f"    ✗ No email revealed for {display}")

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
            print(f"  No contacts found for {domain} — skipping")

    return all_contacts