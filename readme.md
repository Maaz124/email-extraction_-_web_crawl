# Cold Outreach Pipeline

Automates personalised Athena-focused outreach — contact selection from the Athena dataset, website crawling (Crawl4AI), AI email generation (OpenAI), and Gmail sending — all from a single Streamlit UI.

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

## Hands-Free Daily Automation

The Docker deployment runs the scheduler in the background. Choose a compatible
contact CSV in the main control center and click **Start Daily Automation** to
schedule a random daily run between **2:00 PM and 4:00 PM Eastern**. The selected
file and time persist across container restarts, and the pipeline sends up to 40
emails per Eastern calendar day (20 per Gmail account). Click **Stop Automation**
to cancel the next scheduled run, or **Send Now** to run immediately while still
respecting the same daily limits.

## Pipeline Flow (per domain)

```
[A] Load contacts     →  data/athena-dataset.csv
[B] Crawl website     →  Crawl4AI
[C] Generate email    →  OpenAI (personalised per contact)
[D] Send email        →  Gmail API
    Mark domain as emailed  →  data/emailed_log.csv
```

## Contact Source

The default contact source is `data/athena-dataset.csv`; the active source can be
changed from the frontend. A compatible file must include `Company Name`, `First
Name`, `Last Name`, plus email, title, and website/domain columns. Both the Athena
headers (`Email`, `Title`, `Website`) and the legacy headers (`Email Address`,
`Job Title`, `Email Domain`) are supported.

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
│   ├── athena-dataset.csv  ← Active contacts + emails
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
