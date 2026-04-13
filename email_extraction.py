import requests
import json
import time
import csv
import os
import sys
from dotenv import load_dotenv

# --- SETUP ---
load_dotenv()
API_KEY = os.getenv("APOLLO_API_KEY") # ROTATE THIS KEY AFTER TESTING

HEADERS = {
    "Content-Type": "application/json",
    "Cache-Control": "no-cache",
    "X-Api-Key": API_KEY
}

def get_emails_for_company(domain, max_people=5):
    # STEP 1: Search for IDs
    search_url = "https://api.apollo.io/v1/mixed_people/api_search"
    search_payload = {
        "q_organization_domains": domain,
        "page": 1
    }
    
    response = requests.post(search_url, json=search_payload, headers=HEADERS)
    results = response.json()
    people = results.get("people", [])

    extracted_data = []

    # STEP 2: Iterate and Match (Reveal Emails)
    for person in people[:max_people]:
        p_id = person.get("id")
        name = f"{person.get('first_name')} {person.get('last_name_obfuscated')}"
        
        print(f"Fetching email for: {name} at {domain}...")

        match_url = "https://api.apollo.io/v1/people/match"
        match_payload = {"id": p_id}
        
        match_res = requests.post(match_url, json=match_payload, headers=HEADERS)
        
        if match_res.status_code == 200:
            full_data = match_res.json().get("person", {})
            email = full_data.get("email")
            
            if email and email.strip():
                extracted_data.append({
                    "company": domain,
                    "title": full_data.get("title"),
                    "name": f"{full_data.get('first_name')} {full_data.get('last_name')}",
                    "email": email
                })
        
        # Rate limit safety: sleep 1 second between match requests
        time.sleep(1)

    return extracted_data

# Run the script
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python email_extraction.py <input_csv_file> [output_csv_file]")
        sys.exit(1)

    input_csv = sys.argv[1]
    output_csv = sys.argv[2] if len(sys.argv) > 2 else "output.csv"

    domains = []
    try:
        with open(input_csv, mode="r", encoding="utf-8") as file:
            reader = csv.reader(file)
            for row in reader:
                if row:
                    domains.append(row[0].strip())
    except FileNotFoundError:
        print(f"Error: Input file '{input_csv}' not found.")
        sys.exit(1)

    if domains and domains[0].lower() in ['domain', 'website', 'company', 'url', 'websites', 'domains']:
        domains = domains[1:]

    all_contacts = []
    
    for domain in domains:
        print(f"\n--- Processing {domain} ---")
        contacts = get_emails_for_company(domain, max_people=3) # Adjust max_people as needed
        all_contacts.extend(contacts)
    
    # Fallback to test pipeline manually if Apollo comes up entirely empty
    if not all_contacts:
        print("\n[TEST MODE] Apollo returned 0 valid emails. Injecting Ahmad Ahsan for pipeline testing...")
        all_contacts.append({
            "company": domains[0] if domains else "digitalytics.ai",
            "title": "CEO",
            "name": "Ahmad Ahsan",
            "email": "ahmadahsan1997@gmail.com"
        })
        
    print(f"\n--- SAVING TO {output_csv} ---")
    
    with open(output_csv, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["company", "title", "name", "email"])
        writer.writeheader()
        writer.writerows(all_contacts)
        
    print(f"Successfully saved {len(all_contacts)} contacts to {output_csv}.")