"""
ui/app.py
Streamlit front-end for the Digitalytics AI cold-outreach pipeline.

Run from the PROJECT ROOT:
    streamlit run ui/app.py
"""

import sys
import os
from pathlib import Path
from collections import Counter

# ── Make the project root importable so `pipeline` package resolves ──────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import csv
import time
import queue
import threading
import urllib.parse
import concurrent.futures
import logging
import traceback
from io import StringIO
from datetime import datetime

import streamlit as st

# ─── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Digitalytics AI — Cold Outreach",
    page_icon="✉️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.stApp {
    background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 50%, #16213e 100%);
    color: #e2e8f0;
}
section[data-testid="stSidebar"] {
    background: rgba(15,15,30,0.95);
    border-right: 1px solid rgba(99,102,241,0.2);
}

/* Cards */
.card {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(99,102,241,0.2);
    border-radius: 16px;
    padding: 24px;
    margin-bottom: 16px;
    backdrop-filter: blur(10px);
    transition: border-color 0.2s ease;
}
.card:hover { border-color: rgba(99,102,241,0.5); }

/* Step badge */
.step-badge {
    display: inline-flex; align-items: center; justify-content: center;
    width: 32px; height: 32px; border-radius: 50%;
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    color: white; font-weight: 700; font-size: 14px;
    margin-right: 10px; flex-shrink: 0;
}
.step-title {
    display: flex; align-items: center; font-size: 18px;
    font-weight: 600; color: #c7d2fe; margin-bottom: 16px;
}

/* Chips */
.chip { display:inline-flex; align-items:center; gap:6px; padding:4px 12px; border-radius:99px; font-size:12px; font-weight:600; }
.chip-success { background:rgba(16,185,129,0.15); color:#34d399; border:1px solid rgba(16,185,129,0.3); }
.chip-warning { background:rgba(245,158,11,0.15);  color:#fbbf24; border:1px solid rgba(245,158,11,0.3); }
.chip-info    { background:rgba(99,102,241,0.15);   color:#818cf8; border:1px solid rgba(99,102,241,0.3); }
.chip-error   { background:rgba(239,68,68,0.15);    color:#f87171; border:1px solid rgba(239,68,68,0.3); }

/* Email preview */
.email-preview {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(99,102,241,0.15);
    border-radius: 12px; padding: 20px;
    font-size: 14px; line-height: 1.7; color: #cbd5e1;
    white-space: pre-wrap; word-break: break-word; margin-bottom: 12px;
}

/* Buttons */
.stButton > button {
    background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
    color: white !important; border: none !important;
    border-radius: 10px !important; font-weight: 600 !important;
    padding: 10px 24px !important; transition: opacity 0.2s ease !important;
}
.stButton > button:hover { opacity: 0.85 !important; }

/* Metrics */
.metric-box { background:rgba(99,102,241,0.08); border:1px solid rgba(99,102,241,0.2); border-radius:12px; padding:16px; text-align:center; }
.metric-num  { font-size:32px; font-weight:700; color:#818cf8; }
.metric-label{ font-size:12px; color:#94a3b8; margin-top:4px; }

/* Log box */
.log-box {
    background:#0a0a14; border:1px solid rgba(99,102,241,0.15);
    border-radius:10px; padding:16px 20px;
    font-family:'Courier New',monospace; font-size:12px; color:#64748b;
    max-height:320px; overflow-y:auto;
}
.log-box .ok   { color:#34d399; }
.log-box .warn { color:#fbbf24; }
.log-box .info { color:#818cf8; }

hr { border-color:rgba(99,102,241,0.15) !important; }
.stDataFrame { border-radius:10px; overflow:hidden; }
</style>
""", unsafe_allow_html=True)

# ─── Constants ────────────────────────────────────────────────────────────────
TEST_EMAIL       = "maaz.ahmad1862@gmail.com"
DATA_DIR         = PROJECT_ROOT / "data"
EMAILED_LOG_PATH = PROJECT_ROOT / "data" / "emailed_log.csv"
LOGS_DIR         = PROJECT_ROOT / "logs"

def _root(filename: str) -> str:
    return str(PROJECT_ROOT / filename)

# ─── File Logger Setup ────────────────────────────────────────────────────────
LOGS_DIR.mkdir(exist_ok=True)
_log_file = LOGS_DIR / "pipeline.log"

_file_logger = logging.getLogger("pipeline_ui")
if not _file_logger.handlers:                       # avoid duplicate handlers on Streamlit reruns
    _fh = logging.FileHandler(_log_file, encoding="utf-8")
    _fh.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s",
                                       datefmt="%Y-%m-%d %H:%M:%S"))
    _file_logger.addHandler(_fh)
    _file_logger.setLevel(logging.DEBUG)
    _file_logger.propagate = False

# Write a session-start separator once per process (not on every Streamlit rerun)
if not getattr(_file_logger, "_session_started", False):
    _file_logger.info("=" * 70)
    _file_logger.info(f"SESSION START  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    _file_logger.info("=" * 70)
    _file_logger._session_started = True

# ─── Helpers ──────────────────────────────────────────────────────────────────
def load_csv(filepath: str) -> list[dict]:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    except FileNotFoundError:
        return []

def save_csv(filepath: str, rows: list[dict], fieldnames: list[str]) -> None:
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

def log(msg: str, level: str = "info") -> None:
    ts = time.strftime("%H:%M:%S")
    st.session_state.logs.append((ts, level, msg))
    # Mirror every message to the persistent log file
    _lvl_map = {"success": logging.INFO, "warning": logging.WARNING, "error": logging.ERROR}
    _file_logger.log(_lvl_map.get(level, logging.INFO), msg)

def log_exc(msg: str, exc: Exception) -> None:
    """Log a message + full traceback to file; also add short entry to sidebar log."""
    log(f"{msg}: {exc or type(exc).__name__}", "warning")
    _file_logger.error("%s\n%s", msg, traceback.format_exc())

# ─── Emailed-log helpers (Feature 2) ─────────────────────────────────────────
def load_emailed_log() -> set:
    """Return the set of domains already emailed (from emailed_log.csv)."""
    if not EMAILED_LOG_PATH.exists():
        return set()
    try:
        with open(EMAILED_LOG_PATH, "r", encoding="utf-8") as f:
            return {row["domain"] for row in csv.DictReader(f) if row.get("domain")}
    except Exception:
        return set()

def mark_domain_emailed(domain: str) -> None:
    """Append domain + timestamp to emailed_log.csv (creates file if needed)."""
    if not domain:
        return
    DATA_DIR.mkdir(exist_ok=True)
    file_exists = EMAILED_LOG_PATH.exists()
    with open(EMAILED_LOG_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["domain", "emailed_at"])
        if not file_exists:
            writer.writeheader()
        writer.writerow({"domain": domain, "emailed_at": time.strftime("%Y-%m-%d %H:%M:%S")})

# ─── Session State ────────────────────────────────────────────────────────────
_emailed_on_startup = load_emailed_log()

for key, default in {
    "domains":            [],
    "active_domains":     [],        # Feature 1: after limit + skip-emailed filter
    "emailed_domains":    _emailed_on_startup,  # Feature 2: already-emailed set
    "emails_per_company": 3,         # Feature 5: contacts to fetch per domain
    "contacts":           [],
    "crawled":            {},
    "generated_emails":   {},        # real_email -> {subject, body, approved, name, title, company}
    "logs":               [],
    "step":               1,
    "attachment_pdf":     None,      # {"name": str, "bytes": bytes} or None
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ✉️ Cold Outreach")
    st.markdown("**Digitalytics AI** · Automated Pipeline")
    st.markdown("---")

    for num, label in [
        (1, "Configure & Upload"),
        (2, "Run Pipeline"),
        (3, "Review & Send"),
    ]:
        active = st.session_state.step == num
        color  = "#6366f1" if active else "#334155"
        st.markdown(
            f"""<div style="display:flex;align-items:center;gap:10px;padding:8px 0;">
            <div style="width:28px;height:28px;border-radius:50%;background:{color};
                display:flex;align-items:center;justify-content:center;
                font-size:13px;font-weight:700;color:white;flex-shrink:0;">{num}</div>
            <span style="font-size:14px;color:{'#c7d2fe' if active else '#64748b'};
                font-weight:{'600' if active else '400'};">{label}</span></div>""",
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.markdown(
        f"<div class='chip chip-info'>🧪 Test mode — all sends → {TEST_EMAIL}</div>",
        unsafe_allow_html=True,
    )

    if st.session_state.logs:
        st.markdown("### 📋 Activity Log")
        html = "<div class='log-box'>"
        for ts, lvl, msg in st.session_state.logs[-30:]:
            cls = "ok" if lvl == "success" else "warn" if lvl == "warning" else "info"
            html += f"<div><span style='color:#475569'>[{ts}]</span> <span class='{cls}'>{msg}</span></div>"
        html += "</div>"
        st.markdown(html, unsafe_allow_html=True)

# ─── Header ───────────────────────────────────────────────────────────────────
st.markdown("""
<div style="padding:32px 0 8px 0;">
  <h1 style="font-size:36px;font-weight:700;
    background:linear-gradient(135deg,#6366f1,#a78bfa,#38bdf8);
    -webkit-background-clip:text;-webkit-text-fill-color:transparent;margin:0;">
    Cold Outreach Pipeline
  </h1>
  <p style="color:#64748b;margin-top:6px;font-size:15px;">
    Configure · Run · Review · Send — fully automated
  </p>
</div>
""", unsafe_allow_html=True)

# ── Stat bar ──────────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
approved_count = sum(1 for v in st.session_state.generated_emails.values() if v.get("approved"))
for col, num, label in [
    (c1, len(st.session_state.active_domains),   "Active Domains"),
    (c2, len(st.session_state.contacts),          "Contacts"),
    (c3, len(st.session_state.crawled),           "Crawled Sites"),
    (c4, approved_count,                           "Approved Emails"),
]:
    col.markdown(
        f"<div class='metric-box'><div class='metric-num'>{num}</div>"
        f"<div class='metric-label'>{label}</div></div>",
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1 — Configure & Upload
# ═══════════════════════════════════════════════════════════════════════════════
def _parse_domain(website: str) -> str | None:
    parsed = urllib.parse.urlparse(website)
    netloc = parsed.netloc if parsed.netloc else parsed.path.split("/")[0]
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc or None

def _set_domains(raw: list[str]) -> None:
    st.session_state.domains = list(dict.fromkeys(raw))
    DATA_DIR.mkdir(exist_ok=True)
    save_csv(
        str(DATA_DIR / "temp_domains.csv"),
        [{"domain": d} for d in st.session_state.domains],
        ["domain"],
    )
    log(f"Loaded {len(st.session_state.domains)} domains", "success")
    st.session_state.step = max(st.session_state.step, 1)

with st.expander("**Step 1 — Configure & Upload Companies**", expanded=(st.session_state.step == 1)):
    st.markdown("<div class='step-title'><span class='step-badge'>1</span>Choose companies and configure pipeline settings</div>",
                unsafe_allow_html=True)

    tab_up, tab_file, tab_manual = st.tabs(["📁 Upload CSV", "📂 Existing File", "✏️ Manual Entry"])

    # ── Tab 1: Upload ──────────────────────────────────────────────────────────
    with tab_up:
        uploaded = st.file_uploader("CSV with a **Website** column", type=["csv"], key="csv_upload")
        if uploaded and st.button("Parse CSV", key="btn_parse_upload"):
            content = uploaded.read().decode("utf-8")
            domains = [
                d for row in csv.DictReader(StringIO(content))
                if (d := _parse_domain((row.get("Website") or row.get("domain") or "").strip()))
            ]
            if domains:
                _set_domains(domains)
                st.success(f"✅ {len(st.session_state.domains)} domains loaded")
            else:
                st.error("No domains found — check the 'Website' or 'domain' column.")

    # ── Tab 2: Existing file ───────────────────────────────────────────────────
    with tab_file:
        existing = sorted(DATA_DIR.glob("*.csv")) if DATA_DIR.exists() else []
        if existing:
            chosen = st.selectbox("Pick a file from /data/",
                                  [f.name for f in existing], key="sel_existing")
            if st.button("Use This File", key="btn_existing"):
                filepath = DATA_DIR / chosen
                domains = []
                with open(filepath, encoding="utf-8-sig") as f:
                    for row in csv.DictReader(f):
                        # Accept both "Website" (user CSVs) and "domain" (temp_domains.csv)
                        raw = row.get("Website") or row.get("domain") or ""
                        d = _parse_domain(raw.strip())
                        if d:
                            domains.append(d)
                if domains:
                    _set_domains(domains)
                    st.success(f"✅ {len(st.session_state.domains)} domains from {chosen}")
                else:
                    st.error("No domains found.")
        else:
            st.info("No CSV files found in /data/.")

    # ── Tab 3: Manual ─────────────────────────────────────────────────────────
    with tab_manual:
        raw_text = st.text_area("One domain per line", placeholder="example.com\nanother.io",
                                height=120, key="manual_input")
        if st.button("Use These Domains", key="btn_manual"):
            lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
            if lines:
                _set_domains(lines)
                st.success(f"✅ {len(st.session_state.domains)} domains saved")
            else:
                st.error("No domains entered.")

    # ── Settings (shown once domains are loaded) ───────────────────────────────
    if st.session_state.domains:
        st.markdown("---")
        st.markdown("#### ⚙️ Pipeline Settings")

        col_s1, col_s2 = st.columns(2)

        with col_s1:
            # Feature 5: emails per company
            epc = st.number_input(
                "Emails to fetch per company (Apollo)",
                min_value=1,
                max_value=20,
                value=st.session_state.emails_per_company,
                step=1,
                help="How many contacts Apollo will return per domain.",
                key="epc_input",
            )
            st.session_state.emails_per_company = epc

        with col_s2:
            # Feature 1: limit N companies
            limit_val = st.number_input(
                "Limit to first N companies (0 = all)",
                min_value=0,
                value=0,
                step=1,
                help="Set to 0 to process every domain.",
                key="domain_limit_input",
            )

        # Build active_domains: apply limit then skip already-emailed
        candidate_domains = (
            st.session_state.domains[:limit_val]
            if limit_val > 0
            else list(st.session_state.domains)
        )
        active = [d for d in candidate_domains if d not in st.session_state.emailed_domains]
        st.session_state.active_domains = active

        # Feature 2: warn about already-emailed domains
        already_count = len(candidate_domains) - len(active)
        if already_count > 0:
            st.warning(
                f"⚠️ {already_count} of {len(candidate_domains)} selected domain(s) already "
                f"emailed — they will be skipped automatically."
            )

        # Summary
        limit_label = f"first {limit_val}" if limit_val > 0 else "all"
        skip_label  = f", {already_count} skipped (already emailed)" if already_count else ""
        st.info(f"**{len(active)}** domain(s) will be processed ({limit_label} selected{skip_label}).")

        # Domain preview
        preview = " · ".join(f"`{d}`" for d in active[:10])
        extra   = "…" if len(active) > 10 else ""
        if active:
            st.markdown(f"**Active domains ({len(active)}):** {preview}{extra}")

        # ── PDF Attachment ─────────────────────────────────────────────────────
        st.markdown("---")
        st.markdown("#### 📎 Portfolio Attachment (optional)")
        pdf_file = st.file_uploader(
            "Attach a PDF to every outgoing email",
            type=["pdf"],
            key="pdf_upload",
        )
        if pdf_file is not None:
            st.session_state.attachment_pdf = {
                "name": pdf_file.name,
                "bytes": pdf_file.read(),
            }
            st.success(f"✅ **{pdf_file.name}** will be attached to all emails.")
        elif st.session_state.attachment_pdf:
            st.info(f"📎 Current attachment: **{st.session_state.attachment_pdf['name']}**")
            if st.button("Remove attachment", key="btn_remove_pdf"):
                st.session_state.attachment_pdf = None
                st.rerun()

        if st.button("Confirm & Continue →", key="btn_confirm_step1"):
            st.session_state.step = max(st.session_state.step, 2)
            log(f"Confirmed {len(active)} active domains", "success")
            st.success("✅ Settings confirmed. Proceed to Run Pipeline.")

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2 — Run Pipeline (Extract → Crawl → Generate)
# ═══════════════════════════════════════════════════════════════════════════════
with st.expander("**Step 2 — Run Pipeline**", expanded=(st.session_state.step == 2)):
    st.markdown(
        "<div class='step-title'><span class='step-badge'>2</span>"
        "Extract contacts · Crawl websites · Generate emails</div>",
        unsafe_allow_html=True,
    )

    if not st.session_state.active_domains:
        st.warning("Complete Step 1 and confirm your settings first.")
    else:
        active_domains    = st.session_state.active_domains
        emails_per_co     = st.session_state.emails_per_company

        st.markdown(
            f"Ready to process **{len(active_domains)}** domain(s), "
            f"**{emails_per_co}** contact(s) per company."
        )

        run_btn = st.button("▶ Run Full Pipeline", key="btn_run_pipeline")

        # ── Live progress & log placeholders ──────────────────────────────────
        progress_bar = st.progress(0, text="Waiting to start…")
        live_log_box = st.empty()
        _live_lines: list[str] = []

        def _render_log(lines: list[str]) -> None:
            inner = "".join(f"<div>{line}</div>" for line in lines[-60:])
            live_log_box.markdown(
                f"<div class='log-box' style='max-height:320px;'>{inner}</div>",
                unsafe_allow_html=True,
            )

        def _live(msg: str, level: str = "info") -> None:
            log(msg, level)
            css = "ok" if level == "success" else "warn" if level == "warning" else "info"
            ts  = time.strftime("%H:%M:%S")
            _live_lines.append(
                f"<span style='color:#475569'>[{ts}]</span> "
                f"<span class='{css}'>{msg}</span>"
            )
            _render_log(_live_lines)

        # ── Execute pipeline ──────────────────────────────────────────────────
        if run_btn:
            from pipeline.email_extraction import extract_contacts
            from pipeline.crawler          import crawl_domains
            from pipeline.email_generation import generate_email, generate_subject

            total_domains  = len(active_domains)
            STAGE1 = 0.33
            STAGE2 = 0.33
            STAGE3 = 0.34

            # ── Stage 1: Extract contacts ──────────────────────────────────────
            _live(f"⚡ Stage 1/3 — Extracting contacts for {total_domains} domain(s)…")
            progress_bar.progress(0.0, text="Stage 1/3 — Extracting contacts…")

            contacts: list[dict] = []
            try:
                for i, domain in enumerate(active_domains):
                    _live(f"   Fetching contacts for {domain}…")
                    progress_bar.progress(
                        STAGE1 * (i / total_domains),
                        text=f"Stage 1/3 — {domain} ({i+1}/{total_domains})",
                    )

                contacts = extract_contacts(active_domains, max_people=emails_per_co)
                st.session_state.contacts = contacts
                save_csv(_root("emails_output.csv"), contacts, ["company", "title", "name", "email"])

                for c in contacts:
                    _live(
                        f"   ✓ {c.get('name','?')} · {c.get('title','?')} · "
                        f"{c.get('email','?')} ({c.get('company','?')})",
                        "success",
                    )
                _live(f"✅ Stage 1 complete — {len(contacts)} total contact(s)", "success")

            except Exception as exc:
                log_exc("Extraction failed", exc)
                _live(f"❌ Extraction failed: {exc or type(exc).__name__}", "warning")
                st.error(f"Extraction error: {exc or type(exc).__name__}")

            progress_bar.progress(STAGE1, text="Stage 1/3 complete")

            # ── Stage 2: Crawl websites ────────────────────────────────────────
            _live(f"⚡ Stage 2/3 — Crawling {total_domains} website(s)…")
            progress_bar.progress(STAGE1, text="Stage 2/3 — Crawling websites…")

            crawled: dict[str, str] = {}
            try:
                # Capture crawl4ai's stdout in real time via a queue
                _crawl_q: queue.Queue = queue.Queue()
                _crawl_result: dict   = {}
                _crawl_exc            = [None]

                class _StdoutToQueue:
                    """Redirect sys.stdout writes into the queue."""
                    def __init__(self, q, orig): self.q = q; self.orig = orig; self._buf = ""
                    def write(self, text):
                        self.orig.write(text)       # keep terminal output too
                        self._buf += text
                        while "\n" in self._buf:
                            line, self._buf = self._buf.split("\n", 1)
                            if line.strip():
                                self.q.put(line)
                    def flush(self): self.orig.flush()
                    def isatty(self): return False

                def _crawl_worker():
                    import sys as _sys
                    orig = _sys.stdout
                    _sys.stdout = _StdoutToQueue(_crawl_q, orig)
                    try:
                        _crawl_result.update(crawl_domains(active_domains))
                    except Exception as e:
                        _crawl_exc[0] = e
                    finally:
                        _sys.stdout = orig
                        _crawl_q.put(None)          # sentinel: crawl finished

                t = threading.Thread(target=_crawl_worker, daemon=True)
                t.start()

                # Drain the queue and push each line to the live log
                step_i = 0
                while True:
                    try:
                        line = _crawl_q.get(timeout=0.3)
                    except queue.Empty:
                        continue
                    if line is None:                # sentinel received
                        break
                    # Colour-code the crawl4ai status lines
                    lvl = "success" if "✓" in line or "COMPLETE" in line else \
                          "warning" if "✗" in line or "ERROR" in line else "info"
                    _live(f"   {line}", lvl)
                    # Advance progress bar while crawling
                    step_i = min(step_i + 1, total_domains * 4)
                    progress_bar.progress(
                        min(STAGE1 + STAGE2 * (step_i / max(total_domains * 4, 1)), STAGE1 + STAGE2 - 0.01),
                        text=f"Stage 2/3 — crawling…",
                    )

                t.join()

                if _crawl_exc[0] is not None:
                    raise _crawl_exc[0]

                crawled = dict(_crawl_result)
                st.session_state.crawled.update(crawled)
                rows = [{"domain": d, "scraped_content": c}
                        for d, c in st.session_state.crawled.items()]
                save_csv(_root("crawled_output.csv"), rows, ["domain", "scraped_content"])

                for domain, content in crawled.items():
                    words  = len(content.split())
                    status = "warning" if content.startswith("Failed") else "success"
                    _live(f"   ✓ {domain}: {words:,} words scraped", status)
                _live(f"✅ Stage 2 complete — {len(crawled)} site(s) crawled", "success")

            except Exception as exc:
                log_exc("Crawl failed", exc)
                _live(f"❌ Crawl failed: {exc or type(exc).__name__}", "warning")
                st.error(f"Crawl error: {exc or type(exc).__name__} — full traceback saved to logs/pipeline.log")

            progress_bar.progress(STAGE1 + STAGE2, text="Stage 2/3 complete")

            # ── Stage 3: Generate emails ───────────────────────────────────────
            total_contacts = len(st.session_state.contacts)
            _live(f"⚡ Stage 3/3 — Generating emails for {total_contacts} contact(s)…")
            progress_bar.progress(STAGE1 + STAGE2, text="Stage 3/3 — Generating emails…")

            gen_errors: list[str] = []
            for i, c in enumerate(st.session_state.contacts):
                company = c.get("company", "")
                name    = c.get("name", "")
                title   = c.get("title", "")
                email   = c.get("email", "")
                context = st.session_state.crawled.get(company, "No additional context available.")

                _live(f"   Generating email for {name} at {company}…")
                progress_bar.progress(
                    STAGE1 + STAGE2 + STAGE3 * ((i) / max(total_contacts, 1)),
                    text=f"Stage 3/3 — {name} ({i+1}/{total_contacts})",
                )

                try:
                    body    = generate_email(name=name, email=email, title=title,
                                             content=context, company_name=company)
                    subject = generate_subject(body, name, company)
                    st.session_state.generated_emails[email] = {
                        "subject": subject, "body": body, "approved": False,
                        "name": name, "title": title, "company": company,
                        "domain": company,  # company field IS the domain (from Apollo extraction)
                        "real_email": email,
                    }
                    _live(f"   ✓ Draft ready for {name} ({title})", "success")
                except Exception as exc:
                    log_exc(f"Email generation failed for {name}", exc)
                    gen_errors.append(f"{name}: {exc}")
                    _live(f"   ❌ Failed for {name}: {exc or type(exc).__name__}", "warning")

            # ── Pipeline complete ──────────────────────────────────────────────
            total_ready = len(st.session_state.generated_emails)
            progress_bar.progress(1.0, text="Pipeline complete ✓")
            _live(f"🎉 Pipeline complete — {total_ready} email(s) ready to review!", "success")

            if gen_errors:
                st.warning("Some emails failed to generate:\n" + "\n".join(gen_errors))

            st.session_state.step = max(st.session_state.step, 3)
            st.success(
                f"✅ Pipeline done — **{total_ready}** email(s) generated. "
                "Scroll down to **Review & Send**."
            )

        # ── Post-run summary ───────────────────────────────────────────────────
        if st.session_state.contacts or st.session_state.generated_emails:
            st.markdown("---")
            col_a, col_b, col_c = st.columns(3)
            for col, num, label in [
                (col_a, len(st.session_state.contacts),         "Contacts Extracted"),
                (col_b, len(st.session_state.crawled),          "Sites Crawled"),
                (col_c, len(st.session_state.generated_emails), "Emails Generated"),
            ]:
                col.markdown(
                    f"<div class='metric-box'><div class='metric-num'>{num}</div>"
                    f"<div class='metric-label'>{label}</div></div>",
                    unsafe_allow_html=True,
                )

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 3 — Review & Send
# ═══════════════════════════════════════════════════════════════════════════════
with st.expander("**Step 3 — Review & Send**", expanded=(st.session_state.step == 3)):
    st.markdown("<div class='step-title'><span class='step-badge'>3</span>Approve drafts then send</div>",
                unsafe_allow_html=True)

    st.markdown(
        f"<div class='card'><span class='chip chip-warning'>🧪 Test Mode</span>"
        f"&nbsp; All emails will be delivered to <code>{TEST_EMAIL}</code>.</div>",
        unsafe_allow_html=True,
    )

    if not st.session_state.generated_emails:
        st.warning("No emails generated yet — run the pipeline first (Step 2).")
    else:
        col_aa, col_ra = st.columns(2)
        with col_aa:
            if st.button("✅ Approve All", key="btn_approve_all"):
                for k in st.session_state.generated_emails:
                    st.session_state.generated_emails[k]["approved"] = True
                st.success("All approved!")
        with col_ra:
            if st.button("❌ Clear All Approvals", key="btn_clear_all"):
                for k in st.session_state.generated_emails:
                    st.session_state.generated_emails[k]["approved"] = False
                st.info("Approvals cleared.")

        st.markdown("---")

        # ── Per-email cards ────────────────────────────────────────────────────
        for real_email, data in st.session_state.generated_emails.items():
            approved = data.get("approved", False)
            badge    = ("<span class='chip chip-success'>✓ Approved</span>" if approved
                        else "<span class='chip chip-warning'>⏳ Pending</span>")

            st.markdown(
                f"""<div class='card'>
                <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;'>
                    <div>
                        <span style='font-weight:600;color:#c7d2fe;font-size:16px;'>{data['name']}</span>
                        <span style='color:#64748b;font-size:13px;'> · {data['title']} · {data['company']}</span>
                    </div>
                    {badge}
                </div>
                <div style='margin-bottom:6px;'>
                    <span style='color:#94a3b8;font-size:12px;'>TO (TEST):</span>
                    <code style='color:#818cf8;'>{TEST_EMAIL}</code>
                    <span style='color:#475569;font-size:12px;'> (real: {real_email})</span>
                </div>
                </div>""",
                unsafe_allow_html=True,
            )

            new_subject = st.text_input("Subject", value=data["subject"], key=f"subj_{real_email}")
            new_body    = st.text_area("Body",    value=data["body"],    height=220, key=f"body_{real_email}")

            st.session_state.generated_emails[real_email]["subject"] = new_subject
            st.session_state.generated_emails[real_email]["body"]    = new_body

            col_chk, col_btn, _ = st.columns([1, 1, 4])
            with col_chk:
                cb = st.checkbox("Approve", value=approved, key=f"chk_{real_email}")
                st.session_state.generated_emails[real_email]["approved"] = cb
            with col_btn:
                if st.button("Send now →", key=f"send_{real_email}"):
                    if not cb:
                        st.warning("Approve this email first.")
                    else:
                        with st.spinner("Sending…"):
                            try:
                                from pipeline.email_sender import get_gmail_service, send_email
                                svc    = get_gmail_service()
                                att    = st.session_state.attachment_pdf
                                msg_id = send_email(
                                    svc, to=TEST_EMAIL,
                                    subject=new_subject, body=new_body,
                                    attachment_bytes=att["bytes"] if att else None,
                                    attachment_name=att["name"]   if att else "portfolio.pdf",
                                )
                                log(f"Sent for {data['name']} → ID {msg_id}", "success")
                                st.success(f"✅ Sent! ID: {msg_id}")
                                # Feature 2: mark this domain as emailed
                                domain = data.get("domain") or data.get("company", "")
                                if domain:
                                    mark_domain_emailed(domain)
                                    st.session_state.emailed_domains.add(domain)
                                    log(f"Marked {domain} as emailed", "success")
                            except Exception as e:
                                log_exc("Send failed", e)
                                st.error(f"Send failed: {e or type(e).__name__} — see logs/pipeline.log")

            st.markdown("<hr style='margin:16px 0;border-color:rgba(99,102,241,0.1);'>",
                        unsafe_allow_html=True)

        # ── Bulk send ──────────────────────────────────────────────────────────
        approved_map = {k: v for k, v in st.session_state.generated_emails.items()
                        if v.get("approved")}
        st.markdown(
            f"**{len(approved_map)}** / **{len(st.session_state.generated_emails)}** emails approved."
        )
        if st.button(f"🚀 Send All Approved ({len(approved_map)})", key="btn_bulk_send",
                     disabled=len(approved_map) == 0):
            from pipeline.email_sender import get_gmail_service, send_email
            with st.spinner("Sending…"):
                try:
                    svc  = get_gmail_service()
                    att  = st.session_state.attachment_pdf
                    sent = 0
                    errs = []
                    for real_email, data in approved_map.items():
                        try:
                            msg_id = send_email(
                                svc, to=TEST_EMAIL,
                                subject=data["subject"], body=data["body"],
                                attachment_bytes=att["bytes"] if att else None,
                                attachment_name=att["name"]   if att else "portfolio.pdf",
                            )
                            log(f"Bulk sent for {data['name']} → ID {msg_id}", "success")
                            # Feature 2: mark this domain as emailed
                            domain = data.get("domain") or data.get("company", "")
                            if domain:
                                mark_domain_emailed(domain)
                                st.session_state.emailed_domains.add(domain)
                            sent += 1
                        except Exception as e:
                            log_exc(f"Bulk send failed for {data['name']}", e)
                            errs.append(f"{data['name']}: {e}")
                            log(f"Bulk failed for {data['name']}: {e}", "warning")
                    if errs:
                        st.warning(f"Sent {sent}, failed {len(errs)}:\n" + "\n".join(errs))
                    else:
                        st.success(f"✅ {sent} emails sent to {TEST_EMAIL}!")
                        log(f"Marked {sent} domain(s) as emailed", "success")
                except Exception as e:
                    log_exc("Gmail init failed", e)
                    st.error(f"Gmail init failed: {e or type(e).__name__} — see logs/pipeline.log")
