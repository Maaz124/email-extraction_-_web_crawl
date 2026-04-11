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