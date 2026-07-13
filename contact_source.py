"""Persist and validate the contact CSV selected in the frontend."""

import csv
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
CONFIG_FILE = DATA_DIR / "contact_source.json"
DEFAULT_SOURCE = "athena-dataset.csv"
HIDDEN_SOURCES = {"reserved_contacts.csv", "test_contacts.csv", "mock_contacts_backup.csv"}


def _headers(path: Path) -> set[str]:
    try:
        with open(path, encoding="utf-8-sig", newline="") as f:
            return set(csv.DictReader(f).fieldnames or [])
    except (OSError, UnicodeError, csv.Error):
        return set()


def is_compatible_contact_source(path: Path) -> bool:
    headers = _headers(path)
    return (
        {"First Name", "Last Name", "Company Name"}.issubset(headers)
        and bool({"Email", "Email Address"} & headers)
        and bool({"Title", "Job Title"} & headers)
        and bool({"Website", "Email Domain"} & headers)
    )


def list_contact_sources() -> list[Path]:
    if not DATA_DIR.exists():
        return []
    sources = [
        path for path in DATA_DIR.glob("*.csv")
        if path.name not in HIDDEN_SOURCES and is_compatible_contact_source(path)
    ]
    return sorted(sources, key=lambda path: (path.name != DEFAULT_SOURCE, path.name.lower()))


def get_contact_source_file() -> Path:
    filename = DEFAULT_SOURCE
    if CONFIG_FILE.exists():
        try:
            filename = json.loads(CONFIG_FILE.read_text()).get("filename", DEFAULT_SOURCE)
        except (OSError, ValueError, AttributeError):
            filename = DEFAULT_SOURCE

    candidate = DATA_DIR / Path(filename).name
    default = DATA_DIR / DEFAULT_SOURCE
    if candidate.exists() and is_compatible_contact_source(candidate):
        return candidate
    return default


def save_contact_source(filename: str) -> Path:
    if Path(filename).name != filename:
        raise ValueError("Contact source must be a filename from the data directory")
    source = DATA_DIR / filename
    if not source.exists():
        raise FileNotFoundError(source)
    if not is_compatible_contact_source(source):
        raise ValueError("CSV does not contain the required contact, email, title, and website columns")
    CONFIG_FILE.write_text(json.dumps({"filename": filename}, indent=2))
    return source
