# Cold Outreach Pipeline

Automates personalised cold outreach — contact selection from the high-probability buyers CSV, website crawling (Crawl4AI), AI email generation (OpenAI), and Gmail sending — all from a single Streamlit UI.

## Setup

1. `pip install -r req.txt`
2. Create `.env`:
   ```
   APOLLO_API_KEY="your_key"
   CLIENT_ID="your_google_client_id"
   CLIENT_SECRET="your_google_client_secret"
   OPENAI_API_KEY="your_openai_key"
   ```
3. Generate Gmail OAuth tokens:
   ```
   python build-token.py
   python build-token2.py
   ```
   `token2.json` is required for Gmail Account 2. On a server, generate/copy both token files before running the app; the pipeline will not open a browser during normal runs.

## Running

```bash
streamlit run ui/app.py
```

Then follow the 3-step UI: **Configure → Run Pipeline → Review Sent Emails**

## Pipeline Flow (per domain)

```
[A] Load contacts     →  data/high_probability_buyers_sorted_by_title.csv
[B] Crawl website     →  Crawl4AI
[C] Generate email    →  OpenAI (personalised per contact)
[D] Send email        →  Gmail API
    Mark domain as emailed  →  data/emailed_log.csv
```

## Contact Source

The active contact source is `data/high_probability_buyers_sorted_by_title.csv`.
It must include `Email Domain`, `Email Address`, `Company Name`, `First Name`, `Last Name`, and `Job Title`.

## Project Structure

```
cold outreach/
├── build-token.py          ← Gmail OAuth token generator (run once)
├── digit_context.md        ← Digitalytics capability doc fed to LLM
├── readme.md
├── req.txt                 ← Python dependencies
├── .env                    ← API keys (not committed)
├── token.json              ← Gmail OAuth token for account 1 (not committed)
├── token2.json             ← Gmail OAuth token for account 2 (not committed)
│
├── data/
│   ├── companies.csv       ← Full company list
│   ├── companies_1.csv     ← Current working list
│   ├── digilogo.png        ← Logo embedded in outgoing emails
│   ├── high_probability_buyers_sorted_by_title.csv ← Active contacts + emails
│   └── emailed_log.csv     ← Tracks sent domains to prevent duplicates
│
├── pipeline/               ← Core pipeline modules
│   ├── crawler.py          ← Crawl4AI website scraper
│   ├── email_extraction.py ← Apollo contact fetcher
│   ├── email_generation.py ← OpenAI email + subject generator
│   ├── email_sender.py     ← Gmail API sender (HTML template)
│   └── run_pipeline.py     ← CLI runner (optional)
│
├── ui/
│   └── app.py              ← Streamlit dashboard
│
└── logs/
    └── pipeline.log        ← Full run logs
```
