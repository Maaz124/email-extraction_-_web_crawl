"""
pipeline/crawler.py
Crawls a list of domains using crawl4ai and returns a dict of domain -> content.
"""

import asyncio
import io
import sys
import tiktoken
import trafilatura
from crawl4ai import AsyncWebCrawler
from pipeline.log import logger

# Force stdout/stderr to UTF-8 on Windows to avoid cp1252 encoding errors
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

_enc = tiktoken.encoding_for_model("gpt-4o")


async def _crawl_all(domains: list[str]) -> dict[str, str]:
    results: dict[str, str] = {}
    async with AsyncWebCrawler() as crawler:
        for domain in domains:
            url = domain if domain.startswith("http") else f"https://{domain}"
            logger.info(f"[CRAWL] Crawling {url}")
            try:
                result = await crawler.arun(url=url)
                raw_html = (
                    result.html
                    if result and hasattr(result, "html")
                    else None
                )
                if raw_html:
                    extracted = trafilatura.extract(
                        raw_html,
                        include_links=False,
                        include_images=False,
                        no_fallback=False,
                    )
                    if extracted:
                        token_count = len(_enc.encode(extracted))
                        char_count = len(extracted)
                        logger.info(
                            f"[CRAWL] {domain} — trafilatura extracted "
                            f"{char_count} chars / {token_count} tokens"
                        )
                        content = extracted
                    else:
                        logger.warning(f"[CRAWL] {domain} — trafilatura returned no content")
                        content = "No text content extracted."
                else:
                    logger.warning(f"[CRAWL] {domain} — no HTML returned by crawler")
                    content = "No HTML content extracted."
            except Exception as exc:
                safe_exc = str(exc).encode("utf-8", errors="replace").decode("utf-8")
                logger.error(f"[CRAWL] Failed to crawl {url}: {safe_exc}")
                content = f"Failed to crawl: {safe_exc}"
            results[domain] = content
    return results


def crawl_domains(domains: list[str]) -> dict[str, str]:
    """
    Synchronous wrapper around the async crawler.
    Returns {domain: scraped_content}.
    """
    if sys.platform == "win32":
        loop = asyncio.ProactorEventLoop()
        try:
            return loop.run_until_complete(_crawl_all(domains))
        finally:
            loop.close()
    return asyncio.run(_crawl_all(domains))