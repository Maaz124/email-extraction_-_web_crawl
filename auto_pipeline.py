"""
auto_pipeline.py
Headless pipeline runner — no Streamlit, no UI.
Designed to be called by a Linux cron job at 6 AM daily.

Usage:
    PYTHONIOENCODING=utf-8 .venv/bin/python auto_pipeline.py

Cron entry (edit with `crontab -e`):
    0 6 * * * PYTHONIOENCODING=utf-8 /path/to/project/.venv/bin/python /path/to/project/auto_pipeline.py >> /path/to/project/logs/cron.log 2>&1
"""

import sys
import csv
import json
from datetime import datetime
from pathlib import Path

# Ensure project root is importable regardless of cron's working directory
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.email_extraction import extract_contacts, _EXTRACTED_FILE
from pipeline.crawler          import crawl_domains
from pipeline.email_generation import generate_email, generate_subject
from pipeline.email_sender     import get_gmail_service, send_email
from pipeline.log              import logger

# ── Paths & constants ─────────────────────────────────────────────────────────
DATA_DIR        = PROJECT_ROOT / "data"
EMAILED_LOG     = DATA_DIR / "emailed_log.csv"
RATE_LIMIT_FILE = DATA_DIR / "rate_limit.json"
TOKEN_ACCT1     = PROJECT_ROOT / "token.json"
TOKEN_ACCT2     = PROJECT_ROOT / "token2.json"

DAILY_LIMIT    = 40
ACCOUNT1_LIMIT = 20
ACCOUNT2_LIMIT = 20


# ── Rate-limit helpers (mirrors app.py logic, no Streamlit) ───────────────────
def load_rate_limit() -> dict:
    today = datetime.now().strftime("%Y-%m-%d")
    if RATE_LIMIT_FILE.exists():
        try:
            data = json.loads(RATE_LIMIT_FILE.read_text())
            if data.get("date") == today:
                return data
        except Exception:
            pass
    return {"date": today, "account1_sent": 0, "account2_sent": 0}


def save_rate_limit(data: dict) -> None:
    RATE_LIMIT_FILE.write_text(json.dumps(data, indent=2))


def increment_rate_limit(account: int) -> None:
    data = load_rate_limit()
    if account == 1:
        data["account1_sent"] += 1
    else:
        data["account2_sent"] += 1
    save_rate_limit(data)


# ── Emailed-log helpers ────────────────────────────────────────────────────────
def load_emailed_log() -> set:
    if not EMAILED_LOG.exists():
        return set()
    with open(EMAILED_LOG, encoding="utf-8") as f:
        return {r["domain"] for r in csv.DictReader(f) if r.get("domain")}


def mark_domain_emailed(domain: str) -> None:
    file_exists = EMAILED_LOG.exists()
    with open(EMAILED_LOG, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["domain", "emailed_at"])
        if not file_exists:
            w.writeheader()
        w.writerow({"domain": domain,
                    "emailed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})


# ── Domain discovery ──────────────────────────────────────────────────────────
def get_remaining_domains(emailed: set) -> list[str]:
    """Return unique domains from _EXTRACTED_FILE that haven't been emailed yet."""
    if not _EXTRACTED_FILE.exists():
        logger.error(f"[AUTO] Contact file not found: {_EXTRACTED_FILE}")
        return []
    with open(_EXTRACTED_FILE, encoding="utf-8") as f:
        all_domains = list(dict.fromkeys(
            r["Email Domain"] for r in csv.DictReader(f)
            if r.get("Email Domain", "").strip()
        ))
    remaining = [d for d in all_domains if d not in emailed]
    logger.info(
        f"[AUTO] {len(all_domains)} total domains | "
        f"{len(emailed)} already emailed | "
        f"{len(remaining)} remaining"
    )
    return remaining


# ── Main ──────────────────────────────────────────────────────────────────────
def run() -> None:
    logger.info("=" * 60)
    logger.info(f"[AUTO] Pipeline started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Check rate limit before doing anything
    rl = load_rate_limit()
    a1_sent = rl["account1_sent"]
    a2_sent = rl["account2_sent"]
    total_sent = a1_sent + a2_sent
    remaining_sends = DAILY_LIMIT - total_sent

    if remaining_sends <= 0:
        logger.info("[AUTO] Daily limit already reached — nothing to send today.")
        logger.info("=" * 60)
        return

    logger.info(
        f"[AUTO] Rate limit — Acct1: {a1_sent}/{ACCOUNT1_LIMIT} | "
        f"Acct2: {a2_sent}/{ACCOUNT2_LIMIT} | "
        f"Remaining: {remaining_sends}"
    )

    # Init Gmail services
    svc1 = None
    try:
        svc1 = get_gmail_service(token_file=str(TOKEN_ACCT1))
        logger.info("[AUTO] Gmail Account 1 (Ahsan) ready")
    except Exception as e:
        logger.warning(f"[AUTO] Gmail Account 1 init failed: {e}")

    svc2 = None
    try:
        svc2 = get_gmail_service(token_file=str(TOKEN_ACCT2))
        logger.info("[AUTO] Gmail Account 2 (Abdullah) ready")
    except Exception as e:
        logger.error(f"[AUTO] Gmail Account 2 init failed: {e} — aborting run")
        logger.info("=" * 60)
        return

    emailed  = load_emailed_log()
    domains  = get_remaining_domains(emailed)
    grand_sent = 0

    for domain in domains:
        # Re-read rate limit on each domain (UI may be running concurrently)
        rl = load_rate_limit()
        a1_sent = rl["account1_sent"]
        a2_sent = rl["account2_sent"]
        if a1_sent + a2_sent >= DAILY_LIMIT:
            logger.info(f"[AUTO] Daily limit reached — stopping after {grand_sent} sent.")
            break

        logger.info(f"[AUTO] ── Processing: {domain}")

        # A) Extract contacts
        contacts = extract_contacts([domain], max_people=3)
        if not contacts:
            logger.info(f"[AUTO] No contacts for {domain} — skipping")
            continue

        # B) Crawl website
        context = "No additional context available."
        try:
            crawled = crawl_domains([domain])
            context = crawled.get(domain, context)
        except Exception as e:
            logger.warning(f"[AUTO] Crawl failed for {domain}: {e}")

        # C+D) Generate email and send — per contact
        domain_sent = 0
        hard_stop   = False

        for c in contacts:
            rl = load_rate_limit()
            a1_sent = rl["account1_sent"]
            a2_sent = rl["account2_sent"]
            if a1_sent + a2_sent >= DAILY_LIMIT:
                break

            # Pick account (Account 1 first, fall back to Account 2)
            if a1_sent < ACCOUNT1_LIMIT and svc1:
                svc, acct, sender_key = svc1, 1, "account1"
            else:
                svc, acct, sender_key = svc2, 2, "account2"

            try:
                body = generate_email(
                    name=c["name"], email=c["email"], title=c["title"],
                    content=context, company_name=c["company"],
                    greeting=c.get("greeting", ""),
                )
                subject = generate_subject(body, c["name"], c["company"])
                send_email(svc, to=c["email"], subject=subject, body=body,
                           sender_key=sender_key)
                increment_rate_limit(acct)
                grand_sent  += 1
                domain_sent += 1
                logger.info(f"[AUTO] Sent to {c['email']} via {sender_key}")
            except Exception as e:
                logger.error(f"[AUTO] Send failed for {c['email']}: {e}")
                if acct == 2:
                    logger.error("[AUTO] Account 2 hard stop.")
                    hard_stop = True
                    break

        if domain_sent > 0:
            mark_domain_emailed(domain)
            logger.info(f"[AUTO] {domain} marked as emailed ({domain_sent} sent)")

        if hard_stop:
            break

    logger.info(f"[AUTO] Done — {grand_sent} email(s) sent today.")
    logger.info("=" * 60)


if __name__ == "__main__":
    run()
