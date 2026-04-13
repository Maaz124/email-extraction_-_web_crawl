"""
pipeline/run_pipeline.py
CLI orchestrator: parse domains → extract contacts → crawl → generate → send.

Usage:
    python -m pipeline.run_pipeline data/companies.csv
or:
    python pipeline/run_pipeline.py data/companies.csv
"""

import csv
import os
import sys
import urllib.parse
from pathlib import Path

# Allow running as a script from the project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.email_extraction import extract_contacts
from pipeline.crawler import crawl_domains
from pipeline.email_generation import generate_email, generate_subject
from pipeline.email_sender import get_gmail_service, send_email


def parse_domains(companies_csv: str) -> list[str]:
    domains: list[str] = []
    with open(companies_csv, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            website = row.get("Website", "").strip()
            if website:
                parsed = urllib.parse.urlparse(website)
                netloc = parsed.netloc if parsed.netloc else parsed.path.split("/")[0]
                if netloc.startswith("www."):
                    netloc = netloc[4:]
                if netloc:
                    domains.append(netloc)
    return list(dict.fromkeys(domains))  # dedupe, preserve order


def main(companies_csv: str) -> None:
    print(f"[1/4] Parsing domains from {companies_csv}…")
    domains = parse_domains(companies_csv)
    if not domains:
        print("No domains found — check the 'Website' column.")
        sys.exit(1)
    print(f"      {len(domains)} domains found.")

    print("\n[2/4] Extracting contacts via Apollo…")
    contacts = extract_contacts(domains)
    print(f"      {len(contacts)} contacts extracted.")

    print("\n[3/4] Crawling company websites…")
    crawled = crawl_domains(domains)
    print(f"      {len(crawled)} sites crawled.")

    print("\n[4/4] Generating & sending emails…")
    service = get_gmail_service()
    for contact in contacts:
        company = contact["company"]
        name = contact["name"]
        email = contact["email"]
        title = contact["title"]
        content = crawled.get(company, "No additional context available.")
        print(f"\n  → {name} ({title}) at {company}")
        try:
            body = generate_email(name=name, email=email, title=title,
                                  content=content, company_name=company)
            subject = generate_subject(company)
            send_email(service, to=email, subject=subject, body=body)
        except Exception as exc:
            print(f"  ✗ Failed: {exc}")

    print("\nPipeline complete!")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python pipeline/run_pipeline.py <companies_csv>")
        sys.exit(1)
    main(sys.argv[1])
