▶ Run Full Pipeline clicked
│
└─ For each domain (e.g. r1therapeutics.com):
   │
   ├─ [A] Apollo API → fetch up to N contacts
   │         → e.g. john@r1therapeutics.com, jane@r1therapeutics.com
   │
   ├─ [B] Crawl4AI → scrape domain website for context
   │
   ├─ [C] OpenAI → generate personalised email for each contact
   │         → subject + body tailored to their name/title/company
   │
   └─ [D] Gmail API → send email to each contact's real address
             → if all sent: mark domain in emailed_log.csv
             → move to next domain
