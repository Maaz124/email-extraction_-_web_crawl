import csv
import sys
import tempfile
import types
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

# Isolate these unit tests from optional crawler, Gmail, and OpenAI dependencies.
email_extraction = types.ModuleType("pipeline.email_extraction")
email_extraction.extract_contacts = lambda *_args, **_kwargs: []
email_extraction._contact_domain = lambda row: row.get("Website", "")
sys.modules["pipeline.email_extraction"] = email_extraction

crawler = types.ModuleType("pipeline.crawler")
crawler.crawl_domains = lambda _domains: {}
sys.modules["pipeline.crawler"] = crawler

email_generation = types.ModuleType("pipeline.email_generation")
email_generation.generate_email = lambda **_kwargs: ""
email_generation.generate_subject = lambda *_args: ""
sys.modules["pipeline.email_generation"] = email_generation

email_sender = types.ModuleType("pipeline.email_sender")
email_sender.get_gmail_service = lambda **_kwargs: None
email_sender.send_email = lambda *_args, **_kwargs: None
sys.modules["pipeline.email_sender"] = email_sender

log = types.ModuleType("pipeline.log")
log.logger = types.SimpleNamespace(
    info=lambda *_args: None,
    warning=lambda *_args: None,
    error=lambda *_args: None,
)
sys.modules["pipeline.log"] = log

schedule = types.ModuleType("automation_schedule")
schedule.choose_next_run = lambda *_args, **_kwargs: datetime.now()
schedule.display_scheduled_at = str
schedule.eastern_now = datetime.now
schedule.format_scheduled_at = str
schedule.parse_scheduled_at = lambda _value: None
schedule.scheduled_run_was_missed = lambda _value: False
sys.modules["automation_schedule"] = schedule

contact_source = types.ModuleType("contact_source")
contact_source.get_contact_source_file = lambda: Path("unused.csv")
sys.modules["contact_source"] = contact_source

import auto_pipeline


class AutoPipelineTrackingTests(unittest.TestCase):
    def test_processed_log_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            processed_log = Path(directory) / "processed_log.csv"
            with patch.object(auto_pipeline, "PROCESSED_LOG", processed_log):
                auto_pipeline.mark_domain_processed(
                    "example.com", "no_eligible_contacts"
                )

                self.assertEqual(
                    auto_pipeline.load_processed_log(), {"example.com"}
                )
            with processed_log.open(encoding="utf-8") as f:
                row = next(csv.DictReader(f))
            self.assertEqual(row["status"], "no_eligible_contacts")

    def test_remaining_domains_excludes_emailed_and_processed(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "contacts.csv"
            source.write_text(
                "Website,Email\n"
                "emailed.example,a@emailed.example\n"
                "processed.example,b@processed.example\n"
                "remaining.example,c@remaining.example\n",
                encoding="utf-8",
            )
            with patch.object(
                auto_pipeline, "get_contact_source_file", return_value=source
            ):
                remaining = auto_pipeline.get_remaining_domains(
                    {"emailed.example"}, {"processed.example"}
                )

            self.assertEqual(remaining, ["remaining.example"])


if __name__ == "__main__":
    unittest.main()
