"""
pipeline/email_extraction.py
Fetches contacts + emails for a list of domains from a local CSV file.
"""

import csv
from pathlib import Path

_EXTRACTED_FILE = Path(__file__).resolve().parent.parent / "data" / "extracted_emails.csv"

def get_emails_for_company(domain: str, max_people: int = 3) -> list[dict]:
    """
    Query contacts from data/extracted_emails.csv for `domain`.
    Returns a list of dicts with keys: company, title, name, email.
    """
    if not _EXTRACTED_FILE.exists():
        print(f"  [ERROR] {_EXTRACTED_FILE} not found.")
        return []

    try:
        with open(_EXTRACTED_FILE, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = []
            for r in reader:
                if r.get("domain") == domain and r.get("email"):
                    rows.append({
                        "company": r.get("company_name", domain),
                        "title": r.get("title", ""),
                        "name": r.get("contact_name", ""),
                        "email": r.get("email", ""),
                    })
        print(f"  [CSV] {len(rows)} contact(s) found for {domain} in extracted_emails.csv")
        return rows[:max_people]
    except Exception as e:
        print(f"  [CSV ERROR] {e}")
        return []

def extract_contacts(domains: list[str], max_people: int = 3) -> list[dict]:
    """
    Run extraction across multiple domains via the local CSV.
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