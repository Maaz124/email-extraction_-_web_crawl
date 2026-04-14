# Cold Outreach Pipeline

Automates email extraction (Apollo API) and website crawling (Crawl4AI) from a CSV of companies.

## Setup
1. `pip install -r req.txt`
2. Create `.env` file: `APOLLO_API_KEY="your_key"`

## Usage
Run the pipeline with your input CSV (must have a `Website` column):
```bash
python run_pipeline.py companies_1.csv
```

## Outputs
- `emails_output.csv` (Contacts)
- `crawled_output.csv` (Scraped website text)

run build token to gen a token 



structure

cold outreach/
├── build-token.py        ← OAuth token builder (kept)
├── digit_context.md      ← Digitalytics capability doc for LLM
├── readme.md
├── req.txt
├── .env                  ← API keys
├── token.json            ← Gmail OAuth token
├── data/
│   ├── companies.csv     ← Full company list
│   ├── companies_1.csv   ← Current test list
│   ├── digilogo.png      ← Email logo
│   ├── mock_contacts.csv ← Test email bypass
│   └── emailed_log.csv   ← Dedup log
├── pipeline/             ← All pipeline logic
│   ├── crawler.py
│   ├── email_extraction.py
│   ├── email_generation.py
│   ├── email_sender.py
│   └── run_pipeline.py
├── ui/
│   └── app.py
└── logs/
    └── pipeline.log
