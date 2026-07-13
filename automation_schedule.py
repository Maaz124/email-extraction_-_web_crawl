"""Shared Eastern-time scheduling helpers for hands-free outreach."""

import random
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo("America/New_York")
WINDOW_START = time(14, 0)
WINDOW_END = time(16, 0)


def eastern_now() -> datetime:
    return datetime.now(EASTERN)


def normalize_eastern(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=EASTERN)
    return value.astimezone(EASTERN)


def parse_scheduled_at(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return normalize_eastern(datetime.fromisoformat(value))
    except ValueError:
        return None


def format_scheduled_at(value: datetime) -> str:
    return normalize_eastern(value).isoformat(timespec="seconds")


def display_scheduled_at(value: str | None) -> str:
    parsed = parse_scheduled_at(value)
    return parsed.strftime("%Y-%m-%d %I:%M:%S %p ET") if parsed else "Not scheduled"


def choose_next_run(
    now: datetime | None = None,
    *,
    next_day: bool = False,
    rng: random.Random | None = None,
) -> datetime:
    """Choose a random run time inside the 2-4 PM Eastern window."""
    current = normalize_eastern(now) if now else eastern_now()
    generator = rng or random.SystemRandom()
    target_date = current.date() + timedelta(days=1 if next_day else 0)

    start = datetime.combine(target_date, WINDOW_START, tzinfo=EASTERN)
    end = datetime.combine(target_date, WINDOW_END, tzinfo=EASTERN)
    latest = end - timedelta(minutes=1)

    if not next_day and current >= end:
        target_date += timedelta(days=1)
        start = datetime.combine(target_date, WINDOW_START, tzinfo=EASTERN)
        end = datetime.combine(target_date, WINDOW_END, tzinfo=EASTERN)
        latest = end - timedelta(minutes=1)
    elif not next_day:
        # Keep at least one minute between enabling automation and its first run.
        start = max(start, current + timedelta(minutes=1))
        if start > latest:
            target_date += timedelta(days=1)
            start = datetime.combine(target_date, WINDOW_START, tzinfo=EASTERN)
            end = datetime.combine(target_date, WINDOW_END, tzinfo=EASTERN)
            latest = end - timedelta(minutes=1)

    available_seconds = max(0, int((latest - start).total_seconds()))
    return start + timedelta(seconds=generator.randint(0, available_seconds))


def scheduled_run_was_missed(scheduled: datetime, now: datetime | None = None) -> bool:
    """Return True when a due run can no longer start inside today's window."""
    current = normalize_eastern(now) if now else eastern_now()
    selected = normalize_eastern(scheduled)
    today_end = datetime.combine(current.date(), WINDOW_END, tzinfo=EASTERN)
    return selected.date() < current.date() or (current >= today_end and current >= selected)
