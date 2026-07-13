"""Fetch Athena contacts and their emails for a list of company domains."""

import csv
import urllib.parse
from pathlib import Path
from contact_source import get_contact_source_file

RESERVED_STATES = {"Wisconsin", "Indiana", "Illinois"}
_RESERVED_FILE  = Path(__file__).resolve().parent.parent / "data" / "reserved_contacts.csv"


def _write_reserved_row(row: dict) -> None:
    file_exists = _RESERVED_FILE.exists()
    fieldnames = list(row.keys())
    if file_exists:
        with open(_RESERVED_FILE, encoding="utf-8") as f:
            fieldnames = csv.DictReader(f).fieldnames or fieldnames

    reserved_row = dict(row)
    reserved_row.setdefault("Email Address", row.get("Email", ""))
    reserved_row.setdefault("Job Title", row.get("Title", ""))
    reserved_row.setdefault("Email Domain", _contact_domain(row))

    with open(_RESERVED_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        if not file_exists:
            writer.writeheader()
        writer.writerow(reserved_row)


def _normalize_domain(value: str) -> str:
    parsed = urllib.parse.urlparse(value.strip())
    domain = parsed.netloc if parsed.netloc else parsed.path.split("/")[0]
    domain = domain.lower().strip()
    return domain[4:] if domain.startswith("www.") else domain


def _contact_domain(row: dict) -> str:
    """Use the company website when available, otherwise use the email domain."""
    website_domain = _normalize_domain(row.get("Website", ""))
    if website_domain:
        return website_domain
    exported_domain = _normalize_domain(row.get("Email Domain", ""))
    if exported_domain:
        return exported_domain
    email = (row.get("Email") or row.get("Email Address") or "").strip()
    return _normalize_domain(email.rsplit("@", 1)[-1]) if "@" in email else ""


def get_emails_for_company(domain: str, max_people: int = 3, _reserved_seen: set | None = None) -> list[dict]:
    """
    Query contacts from the Athena CSV for `domain`.
    Returns contact details using the Athena export's Email, Title, and Website fields.
    """
    extracted_file = get_contact_source_file()
    if not extracted_file.exists():
        print(f"  [ERROR] {extracted_file} not found.")
        return []

    requested_domain = _normalize_domain(domain)

    try:
        with open(extracted_file, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = []
            for r in reader:
                row_domains = {
                    _contact_domain(r),
                    _normalize_domain(r.get("Website", "")),
                }
                email_addr = (r.get("Email") or r.get("Email Address") or "").strip()
                if requested_domain in row_domains and email_addr:
                    state = r.get("Company State", "").strip()
                    if state in RESERVED_STATES:
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
                        "domain":   requested_domain,
                        "company":  r.get("Company Name", domain),
                        "title":    r.get("Title") or r.get("Job Title", ""),
                        "name":     f"{first_name} {last_name}".strip(),
                        "email":    email_addr,
                        "website":  r.get("Website", "").strip(),
                        "greeting": greeting,
                    })
        print(f"  [CSV] {len(rows)} contact(s) found for {domain} in {extracted_file.name}")
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
                _reserved_seen.add(_row.get("Email", "") or _row.get("Email Address", ""))

    all_contacts: list[dict] = []
    for domain in domains:
        print(f"\n--- Processing {domain} ---")
        contacts = get_emails_for_company(domain, max_people=max_people, _reserved_seen=_reserved_seen)
        if contacts:
            all_contacts.extend(contacts)
        else:
            print(f"  No contacts found for {domain} — skipping")

    return all_contacts
