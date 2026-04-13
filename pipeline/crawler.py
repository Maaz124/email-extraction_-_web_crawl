"""
pipeline/crawler.py
Crawls a list of domains using crawl4ai and returns a dict of domain -> content.
"""

import asyncio
from crawl4ai import AsyncWebCrawler


async def _crawl_all(domains: list[str]) -> dict[str, str]:
    results: dict[str, str] = {}
    async with AsyncWebCrawler() as crawler:
        for domain in domains:
            url = domain if domain.startswith("http") else f"https://{domain}"
            print(f"  Crawling {url}…")
            try:
                result = await crawler.arun(url=url)
                content = (
                    result.markdown
                    if result and hasattr(result, "markdown")
                    else "No markdown content extracted."
                )
            except Exception as exc:
                print(f"  Failed to crawl {url}: {exc}")
                content = f"Failed to crawl: {exc}"
            results[domain] = content
    return results


def crawl_domains(domains: list[str]) -> dict[str, str]:
    """
    Synchronous wrapper around the async crawler.
    Returns {domain: scraped_content}.
    """
    return asyncio.run(_crawl_all(domains))