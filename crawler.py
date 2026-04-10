import asyncio
import sys
import csv
from crawl4ai import AsyncWebCrawler

async def main(input_csv, output_md):
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

    async with AsyncWebCrawler() as crawler:
        with open(output_md, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["domain", "scraped_content"])
            for domain in domains:
                url = domain if domain.startswith("http") else f"https://{domain}"
                print(f"Crawling {url}...")
                content = ""
                try:
                    result = await crawler.arun(url=url)
                    if result and hasattr(result, 'markdown'):
                        content = result.markdown
                    else:
                        content = "No markdown content extracted."
                except Exception as e:
                    print(f"Failed to crawl {url}: {e}")
                    content = f"Failed to crawl: {e}"
                
                writer.writerow([domain, content])
        
    print(f"Crawling completed. Results saved to {output_md}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python crawler.py <input_csv_file> [output_csv_file]")
        sys.exit(1)
        
    input_csv = sys.argv[1]
    output_csv = sys.argv[2] if len(sys.argv) > 2 else "crawled_output.csv"
    
    asyncio.run(main(input_csv, output_csv))