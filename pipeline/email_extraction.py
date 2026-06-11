"""
pipeline/email_extraction.py
Fetches contacts + emails for a list of domains from a local CSV file.
"""

import csv
from pathlib import Path

_EXTRACTED_FILE = Path(__file__).resolve().parent.parent / "data" / "test_contacts.csv"

RESERVED_STATES = {"Wisconsin", "Indiana", "Illinois"}
_RESERVED_FILE  = Path(__file__).resolve().parent.parent / "data" / "reserved_contacts.csv"


def _write_reserved_row(row: dict) -> None:
    file_exists = _RESERVED_FILE.exists()
    with open(_RESERVED_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=row.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def get_emails_for_company(domain: str, max_people: int = 3, _reserved_seen: set | None = None) -> list[dict]:
    """
    Query contacts from the ZoomInfo CSV for `domain`.
    Returns a list of dicts with keys: domain, company, title, name, email, greeting.
    """
    if not _EXTRACTED_FILE.exists():
        print(f"  [ERROR] {_EXTRACTED_FILE} not found.")
        return []

    try:
        with open(_EXTRACTED_FILE, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = []
            for r in reader:
                if r.get("Email Domain") == domain and r.get("Email Address"):
                    state = r.get("Company State", "").strip()
                    if state in RESERVED_STATES:
                        email_addr = r.get("Email Address", "")
                        if _reserved_seen is not None and email_addr not in _reserved_seen:
                            _write_reserved_row(r)
                            _reserved_seen.add(email_addr)
                        print(f"  [RESERVED] {r.get('First Name','')} {r.get('Last Name','')} ({state}) — skipped, saved to reserved_contacts.csv")
                        continue
                    first_name = r.get("First Name", "").strip()
                    last_name  = r.get("Last Name", "").strip()
                    salutation = r.get("Salutation", "").strip()
                    greeting   = f"Hi Dr. {last_name}," if salutation == "Dr." else f"Hi {first_name},"
                    rows.append({
                        "domain":   r.get("Email Domain", ""),
                        "company":  r.get("Company Name", domain),
                        "title":    r.get("Job Title", ""),
                        "name":     f"{first_name} {last_name}".strip(),
                        "email":    r.get("Email Address", ""),
                        "greeting": greeting,
                    })
        print(f"  [CSV] {len(rows)} contact(s) found for {domain} in {_EXTRACTED_FILE.name}")
        return rows[:max_people]
    except Exception as e:
        print(f"  [CSV ERROR] {e}")
        return []

def extract_contacts(domains: list[str], max_people: int = 3) -> list[dict]:
    """
    Run extraction across multiple domains via the local CSV.
    """
    _reserved_seen: set[str] = set()
    if _RESERVED_FILE.exists():
        with open(_RESERVED_FILE, encoding="utf-8") as _f:
            for _row in csv.DictReader(_f):
                _reserved_seen.add(_row.get("Email Address", ""))

    all_contacts: list[dict] = []
    for domain in domains:
        print(f"\n--- Processing {domain} ---")
        contacts = get_emails_for_company(domain, max_people=max_people, _reserved_seen=_reserved_seen)
        if contacts:
            all_contacts.extend(contacts)
        else:
            print(f"  No contacts found for {domain} — skipping")

    return all_contacts