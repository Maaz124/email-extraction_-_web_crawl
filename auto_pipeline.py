"""
auto_pipeline.py
Headless pipeline runner — no Streamlit, no UI.
Designed to be polled by the deployed background scheduler. When enabled,
one random daily run is scheduled between 2:00 PM and 4:00 PM Eastern.
"""

import sys
import csv
import fcntl
import json
from pathlib import Path

# Ensure project root is importable regardless of cron's working directory
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.email_extraction import extract_contacts, _contact_domain
from pipeline.crawler          import crawl_domains
from pipeline.email_generation import generate_email, generate_subject
from pipeline.email_sender     import get_gmail_service, send_email
from pipeline.log              import logger
from automation_schedule import (
    choose_next_run,
    display_scheduled_at,
    eastern_now,
    format_scheduled_at,
    parse_scheduled_at,
    scheduled_run_was_missed,
)
from contact_source import get_contact_source_file

# ── Paths & constants ─────────────────────────────────────────────────────────
DATA_DIR        = PROJECT_ROOT / "data"
EMAILED_LOG     = DATA_DIR / "emailed_log.csv"
PROCESSED_LOG   = DATA_DIR / "processed_log.csv"
RATE_LIMIT_FILE = DATA_DIR / "rate_limit.json"
AUTOMATION_FILE = DATA_DIR / "automation_state.json"
RUN_LOCK_FILE   = DATA_DIR / "outreach_run.lock"
TOKEN_ACCT1     = PROJECT_ROOT / "token.json"
TOKEN_ACCT2     = PROJECT_ROOT / "token2.json"

DAILY_LIMIT    = 40
ACCOUNT1_LIMIT = 20
ACCOUNT2_LIMIT = 20


# ── Automation-state helpers ─────────────────────────────────────────────────
def _now_str() -> str:
    return format_scheduled_at(eastern_now())


def load_automation_state() -> dict:
    if AUTOMATION_FILE.exists():
        try:
            data = json.loads(AUTOMATION_FILE.read_text())
            return {
                "enabled": bool(data.get("enabled", False)),
                "last_run_at": data.get("last_run_at"),
                "next_run_at": data.get("next_run_at"),
                "updated_at": data.get("updated_at"),
                "updated_by": data.get("updated_by", "unknown"),
            }
        except Exception:
            pass
    return {
        "enabled": False,
        "last_run_at": None,
        "next_run_at": None,
        "updated_at": None,
        "updated_by": "default",
    }


def save_automation_state(state: dict) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    AUTOMATION_FILE.write_text(json.dumps(state, indent=2))


def mark_automation_run_started(state: dict) -> None:
    now = eastern_now()
    state["last_run_at"] = format_scheduled_at(now)
    state["next_run_at"] = format_scheduled_at(choose_next_run(now, next_day=True))
    state["updated_at"] = format_scheduled_at(now)
    state["updated_by"] = "auto_pipeline"
    save_automation_state(state)


def ensure_next_run(state: dict) -> bool:
    """Persist a schedule for enabled legacy or newly created state."""
    if parse_scheduled_at(state.get("next_run_at")):
        return False
    state["next_run_at"] = format_scheduled_at(choose_next_run())
    state["updated_at"] = _now_str()
    state["updated_by"] = "auto_pipeline"
    save_automation_state(state)
    return True


def automation_due(state: dict) -> bool:
    next_run_at = parse_scheduled_at(state.get("next_run_at"))
    return next_run_at is not None and eastern_now() >= next_run_at


def reschedule_missed_run(state: dict) -> bool:
    next_run_at = parse_scheduled_at(state.get("next_run_at"))
    if not next_run_at or not scheduled_run_was_missed(next_run_at):
        return False
    state["next_run_at"] = format_scheduled_at(choose_next_run())
    state["updated_at"] = _now_str()
    state["updated_by"] = "auto_pipeline"
    save_automation_state(state)
    logger.info(f"[AUTO] Missed send window; rescheduled for {display_scheduled_at(state['next_run_at'])}")
    return True


# ── Rate-limit helpers (mirrors app.py logic, no Streamlit) ───────────────────
def load_rate_limit() -> dict:
    today = eastern_now().strftime("%Y-%m-%d")
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
                    "emailed_at": eastern_now().strftime("%Y-%m-%d %H:%M:%S ET")})


def load_processed_log() -> set[str]:
    """Load domains with a permanent, non-send outcome."""
    if not PROCESSED_LOG.exists():
        return set()
    with open(PROCESSED_LOG, encoding="utf-8") as f:
        return {r["domain"] for r in csv.DictReader(f) if r.get("domain")}


def mark_domain_processed(domain: str, status: str) -> None:
    """Persist a terminal outcome so the same domain is not retried forever."""
    file_exists = PROCESSED_LOG.exists()
    with open(PROCESSED_LOG, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["domain", "status", "processed_at"])
        if not file_exists:
            w.writeheader()
        w.writerow({
            "domain": domain,
            "status": status,
            "processed_at": eastern_now().strftime("%Y-%m-%d %H:%M:%S ET"),
        })


# ── Domain discovery ──────────────────────────────────────────────────────────
def get_remaining_domains(emailed: set, processed: set | None = None) -> list[str]:
    """Return unique domains from the selected contact file that haven't been emailed."""
    processed = processed or set()
    extracted_file = get_contact_source_file()
    if not extracted_file.exists():
        logger.error(f"[AUTO] Contact file not found: {extracted_file}")
        return []
    with open(extracted_file, encoding="utf-8-sig") as f:
        all_domains = list(dict.fromkeys(
            domain for r in csv.DictReader(f)
            if (domain := _contact_domain(r))
        ))
    completed = emailed | processed
    remaining = [d for d in all_domains if d not in completed]
    logger.info(
        f"[AUTO] {len(all_domains)} total domains | "
        f"{len(emailed)} already emailed | "
        f"{len(processed)} completed without sends | "
        f"{len(remaining)} remaining"
    )
    return remaining


# ── Main ──────────────────────────────────────────────────────────────────────
def run(force: bool = False) -> int:
    """Run scheduled or manual outreach, preventing concurrent send batches."""
    DATA_DIR.mkdir(exist_ok=True)
    with open(RUN_LOCK_FILE, "w", encoding="utf-8") as lock_file:
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            logger.warning("[OUTREACH] Another send run is already active; skipping this request")
            return 0
        return _run(force=force)


def _run(force: bool = False) -> int:
    automation_state = load_automation_state()
    if not force:
        if not automation_state.get("enabled"):
            return 0

        if ensure_next_run(automation_state):
            logger.info(f"[AUTO] Scheduled next run for {display_scheduled_at(automation_state['next_run_at'])}")

        if reschedule_missed_run(automation_state):
            return 0

        if not automation_due(automation_state):
            return 0

    logger.info("=" * 60)
    if force:
        logger.info(f"[MANUAL] Send Now triggered at {eastern_now().strftime('%Y-%m-%d %H:%M:%S ET')}")
    else:
        logger.info(f"[AUTO] Scheduler triggered at {eastern_now().strftime('%Y-%m-%d %H:%M:%S ET')}")
        logger.info("[AUTO] Scheduled time reached; beginning today's outreach run")
        mark_automation_run_started(automation_state)

    # Check rate limit before doing anything
    rl = load_rate_limit()
    a1_sent = rl["account1_sent"]
    a2_sent = rl["account2_sent"]
    total_sent = a1_sent + a2_sent
    remaining_sends = DAILY_LIMIT - total_sent

    if remaining_sends <= 0:
        logger.info("[AUTO] Daily limit already reached — nothing to send today.")
        logger.info("=" * 60)
        return 0

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
        return 0

    emailed   = load_emailed_log()
    processed = load_processed_log()
    domains   = get_remaining_domains(emailed, processed)
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
            mark_domain_processed(domain, "no_eligible_contacts")
            logger.info(f"[AUTO] No eligible contacts for {domain} — marked processed")
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
            elif a2_sent < ACCOUNT2_LIMIT and svc2:
                svc, acct, sender_key = svc2, 2, "account2"
            else:
                logger.warning("[AUTO] No authenticated Gmail account has send capacity remaining")
                hard_stop = True
                break

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
    return grand_sent


if __name__ == "__main__":
    run()
