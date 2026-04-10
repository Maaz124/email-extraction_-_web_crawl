import csv
import subprocess
import os
import urllib.parse
import sys

def main():
    if len(sys.argv) < 2:
        print("Usage: python run_pipeline.py <companies_csv>")
        sys.exit(1)

    companies_csv = sys.argv[1]
    
    # 1. Parse domains
    domains = []
    print(f"Extracting domains from {companies_csv}...")
    try:
        with open(companies_csv, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                website = row.get("Website", "").strip()
                if website:
                    parsed = urllib.parse.urlparse(website)
                    netloc = parsed.netloc if parsed.netloc else parsed.path.split('/')[0]
                    if netloc.startswith("www."):
                        netloc = netloc[4:]
                    if netloc:
                        domains.append(netloc)
    except FileNotFoundError:
        print(f"Error: {companies_csv} not found.")
        sys.exit(1)

    if not domains:
        print("No domains found in the 'Website' column.")
        sys.exit(1)
        
    temp_domains_file = "temp_domains.csv"
    with open(temp_domains_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["domain"])
        for d in domains:
            writer.writerow([d])

    print(f"Found {len(domains)} domains. Saved to {temp_domains_file}")
    
    # 2. Run email extraction
    emails_csv = "emails_output.csv"
    print(f"\n--- Running Email Extraction ---")
    subprocess.run([sys.executable, "email_extraction.py", temp_domains_file, emails_csv])
    
    # 3. Run crawler
    crawler_csv = "crawled_output.csv"
    print(f"\n--- Running Crawler ---")
    subprocess.run([sys.executable, "crawler.py", temp_domains_file, crawler_csv])
    
    print(f"\nPipeline finished!")
    print(f"Emails saved to {emails_csv}")
    print(f"Crawler data saved to {crawler_csv}")

if __name__ == "__main__":
    main()
