"""
batch_extract_emails.py
Standalone script to bulk-extract emails from companies_1.csv using the Apollo API.

Reads every company row, pulls contacts via Apollo, and saves
(domain, company_name, linkedin, contact_name, title, email) to a CSV.

Usage:
    python batch_extract_emails.py                          # default: companies_1.csv → extracted_emails.csv
    python batch_extract_emails.py --input data/companies.csv --output my_emails.csv --max-contacts 5

Features:
    • Resume support — skips domains already present in the output CSV
    • Incremental saves — writes after every domain so no data is lost on crash
    • Progress display in terminal
"""

import argparse
import csv
import os
import sys
import time
import urllib.parse
from pathlib import Path

# ── Ensure project root is importable ────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv()

from pipeline.email_extraction import get_emails_for_company

# ── Helpers ──────────────────────────────────────────────────────────────────

OUTPUT_FIELDS = [
    "domain",
    "company_name",
    "linkedin",
    "contact_name",
    "title",
    "email",
]


def parse_domain(website: str) -> str | None:
    """Extract bare domain from a URL string."""
    website = website.strip()
    if not website:
        return None
    parsed = urllib.parse.urlparse(website)
    netloc = parsed.netloc if parsed.netloc else parsed.path.split("/")[0]
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc or None


def load_existing_domains(output_path: str) -> set[str]:
    """Return the set of domains already present in the output CSV (for resume)."""
    if not os.path.exists(output_path):
        return set()
    try:
        with open(output_path, "r", encoding="utf-8") as f:
            return {row["domain"] for row in csv.DictReader(f) if row.get("domain")}
    except Exception:
        return set()


def append_rows(output_path: str, rows: list[dict]) -> None:
    """Append rows to the output CSV, creating the file + header if needed."""
    file_exists = os.path.exists(output_path) and os.path.getsize(output_path) > 0
    with open(output_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS)
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Bulk-extract emails from a Crunchbase-style companies CSV via Apollo."
    )
    parser.add_argument(
        "-i", "--input",
        default=str(PROJECT_ROOT / "data" / "companies_1.csv"),
        help="Path to the input companies CSV (default: data/companies_1.csv)",
    )
    parser.add_argument(
        "-o", "--output",
        default=str(PROJECT_ROOT / "data" / "extracted_emails.csv"),
        help="Path to the output CSV (default: data/extracted_emails.csv)",
    )
    parser.add_argument(
        "-n", "--max-contacts",
        type=int,
        default=3,
        help="Max contacts to pull per domain (default: 3)",
    )
    args = parser.parse_args()

    input_path  = args.input
    output_path = args.output
    max_contacts = args.max_contacts

    # ── Load input CSV ────────────────────────────────────────────────────────
    if not os.path.exists(input_path):
        print(f"❌ Input file not found: {input_path}")
        sys.exit(1)

    with open(input_path, "r", encoding="utf-8-sig") as f:
        companies = list(csv.DictReader(f))

    if not companies:
        print("❌ Input CSV is empty.")
        sys.exit(1)

    print(f"📄 Loaded {len(companies)} companies from {input_path}")

    # ── Build lookup: domain → (company_name, linkedin) ───────────────────────
    domain_info: dict[str, dict] = {}
    for row in companies:
        website = row.get("Website") or row.get("domain") or ""
        domain = parse_domain(website)
        if not domain:
            continue
        domain_info[domain] = {
            "company_name": row.get("Organization Name", ""),
            "linkedin": row.get("LinkedIn", ""),
        }

    all_domains = list(domain_info.keys())
    print(f"🔗 Parsed {len(all_domains)} unique domains")

    # ── Resume support ────────────────────────────────────────────────────────
    already_done = load_existing_domains(output_path)
    pending = [d for d in all_domains if d not in already_done]

    if already_done:
        print(f"⏩ Skipping {len(already_done)} already-extracted domain(s)")

    if not pending:
        print("✅ All domains already extracted — nothing to do!")
        sys.exit(0)

    print(f"🚀 Starting extraction for {len(pending)} domain(s), max {max_contacts} contacts each\n")

    # ── Extract loop ──────────────────────────────────────────────────────────
    total = len(pending)
    total_contacts = 0
    total_errors = 0

    for idx, domain in enumerate(pending, start=1):
        info = domain_info[domain]
        company_name = info["company_name"]
        linkedin = info["linkedin"]

        print(f"[{idx}/{total}] 🔍 {domain} ({company_name})")

        try:
            contacts = get_emails_for_company(domain, max_people=max_contacts)
        except Exception as exc:
            print(f"  ❌ Error: {exc}")
            total_errors += 1
            continue

        if not contacts:
            print(f"  ⚠️  No contacts found — skipping")
            # Still record the domain with empty contact info so we don't retry
            append_rows(output_path, [{
                "domain": domain,
                "company_name": company_name,
                "linkedin": linkedin,
                "contact_name": "",
                "title": "",
                "email": "",
            }])
            continue

        rows_to_write = []
        for c in contacts:
            email = c.get("email", "")
            name  = c.get("name", "")
            title = c.get("title", "")
            print(f"  ✅ {name} · {title} · {email}")
            rows_to_write.append({
                "domain": domain,
                "company_name": company_name,
                "linkedin": linkedin,
                "contact_name": name,
                "title": title,
                "email": email,
            })

        append_rows(output_path, rows_to_write)
        total_contacts += len(rows_to_write)
        print(f"  → {len(rows_to_write)} contact(s) saved\n")

        # Small delay between domains for rate-limiting
        if idx < total:
            time.sleep(1)

    # ── Summary ───────────────────────────────────────────────────────────────
    print("=" * 50)
    print(f"🎉 Done!")
    print(f"   Domains processed : {total}")
    print(f"   Contacts extracted: {total_contacts}")
    print(f"   Errors            : {total_errors}")
    print(f"   Output saved to   : {output_path}")
    print("=" * 50)


if __name__ == "__main__":
    main()
