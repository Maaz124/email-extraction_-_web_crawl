"""
pipeline/crawler.py
Crawls a list of domains using crawl4ai and returns a dict of domain -> content.
"""

import asyncio
import sys
import tiktoken
import trafilatura
from crawl4ai import AsyncWebCrawler
from pipeline.log import logger

_enc = None


def _count_tokens(content: str) -> int:
    """Count tokens for logging, falling back safely if tokenizer data is unavailable."""
    global _enc
    if _enc is False:
        return max(1, len(content) // 4)
    try:
        if _enc is None:
            _enc = tiktoken.encoding_for_model("gpt-4o")
        return len(_enc.encode(content))
    except Exception as exc:
        logger.warning(f"[CRAWL] Tokenizer unavailable; using character estimate: {exc}")
        _enc = False
        return max(1, len(content) // 4)


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
                        token_count = _count_tokens(extracted)
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
                logger.error(f"[CRAWL] Failed to crawl {url}: {exc}")
                content = f"Failed to crawl: {exc}"
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
