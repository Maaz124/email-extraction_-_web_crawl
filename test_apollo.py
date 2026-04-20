import os
from pipeline.email_extraction import extract_contacts

print("Loaded APOLLO_API_KEY length:", len(os.getenv("APOLLO_API_KEY", "")) if os.getenv("APOLLO_API_KEY") else "None")
domains = ["carecubes.com", "google.com"]
contacts = extract_contacts(domains)
print(contacts)
