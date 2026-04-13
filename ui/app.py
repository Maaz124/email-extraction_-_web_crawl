"""
ui/app.py
Streamlit front-end for the Digitalytics AI cold-outreach pipeline.

Run from the PROJECT ROOT:
    streamlit run ui/app.py
"""

import sys
import os
from pathlib import Path

# ── Make the project root importable so `pipeline` package resolves ──────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import csv
import time
import urllib.parse
from io import StringIO

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
    max-height:240px; overflow-y:auto;
}
.log-box .ok   { color:#34d399; }
.log-box .warn { color:#fbbf24; }
.log-box .info { color:#818cf8; }

hr { border-color:rgba(99,102,241,0.15) !important; }
.stDataFrame { border-radius:10px; overflow:hidden; }
</style>
""", unsafe_allow_html=True)

# ─── Constants ────────────────────────────────────────────────────────────────
TEST_EMAIL = "maaz.ahmad1862@gmail.com"
DATA_DIR   = PROJECT_ROOT / "data"

def _root(filename: str) -> str:
    return str(PROJECT_ROOT / filename)

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

# ─── Session State ────────────────────────────────────────────────────────────
for key, default in {
    "domains":          [],
    "contacts":         [],
    "crawled":          {},
    "generated_emails": {},   # real_email -> {subject, body, approved, name, title, company}
    "logs":             [],
    "step":             1,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ✉️ Cold Outreach")
    st.markdown("**Digitalytics AI** · Semi-Automated Pipeline")
    st.markdown("---")

    for num, label in [
        (1, "Upload Companies"),
        (2, "Extract Contacts"),
        (3, "Crawl Websites"),
        (4, "Generate Emails"),
        (5, "Review & Send"),
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
    Upload · Extract · Crawl · Generate · Send — all in one place
  </p>
</div>
""", unsafe_allow_html=True)

# ── Stat bar ──────────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
approved_count = sum(1 for v in st.session_state.generated_emails.values() if v.get("approved"))
for col, num, label in [
    (c1, len(st.session_state.domains),          "Domains"),
    (c2, len(st.session_state.contacts),         "Contacts"),
    (c3, len(st.session_state.crawled),          "Crawled Sites"),
    (c4, approved_count,                          "Approved Emails"),
]:
    col.markdown(
        f"<div class='metric-box'><div class='metric-num'>{num}</div>"
        f"<div class='metric-label'>{label}</div></div>",
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1 — Upload / Enter Domains
# ═══════════════════════════════════════════════════════════════════════════════
def _parse_domain(website: str) -> str | None:
    parsed = urllib.parse.urlparse(website)
    netloc = parsed.netloc if parsed.netloc else parsed.path.split("/")[0]
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc or None

def _set_domains(raw: list[str]) -> None:
    st.session_state.domains = list(dict.fromkeys(raw))
    save_csv(
        _root("temp_domains.csv"),
        [{"domain": d} for d in st.session_state.domains],
        ["domain"],
    )
    log(f"Loaded {len(st.session_state.domains)} domains", "success")
    st.session_state.step = max(st.session_state.step, 2)

with st.expander("**Step 1 — Upload Companies CSV**", expanded=(st.session_state.step == 1)):
    st.markdown("<div class='step-title'><span class='step-badge'>1</span>Choose your companies list</div>",
                unsafe_allow_html=True)

    tab_up, tab_file, tab_manual = st.tabs(["📁 Upload CSV", "📂 Existing File", "✏️ Manual Entry"])

    # ── Tab 1: Upload ──────────────────────────────────────────────────────────
    with tab_up:
        uploaded = st.file_uploader("CSV with a **Website** column", type=["csv"], key="csv_upload")
        if uploaded and st.button("Parse CSV", key="btn_parse_upload"):
            content = uploaded.read().decode("utf-8")
            domains = [
                d for row in csv.DictReader(StringIO(content))
                if (d := _parse_domain(row.get("Website", "").strip()))
            ]
            if domains:
                _set_domains(domains)
                st.success(f"✅ {len(st.session_state.domains)} domains loaded")
            else:
                st.error("No domains found — check the 'Website' column.")

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
                        d = _parse_domain(row.get("Website", "").strip())
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

    if st.session_state.domains:
        preview = " · ".join(f"`{d}`" for d in st.session_state.domains[:10])
        extra   = "…" if len(st.session_state.domains) > 10 else ""
        st.markdown(f"**Domains ({len(st.session_state.domains)}):** {preview}{extra}")

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2 — Extract Contacts
# ═══════════════════════════════════════════════════════════════════════════════
with st.expander("**Step 2 — Extract Contacts via Apollo**", expanded=(st.session_state.step == 2)):
    st.markdown("<div class='step-title'><span class='step-badge'>2</span>Pull contacts for each domain</div>",
                unsafe_allow_html=True)

    if not st.session_state.domains:
        st.warning("Complete Step 1 first.")
    else:
        max_people = st.slider("Max contacts per domain", 1, 10, 3, key="max_people")

        col_run, col_load = st.columns(2)
        with col_run:
            if st.button("▶ Run Extraction", key="btn_extract"):
                from pipeline.email_extraction import extract_contacts
                with st.spinner("Querying Apollo…"):
                    log("Starting Apollo extraction…")
                    try:
                        contacts = extract_contacts(st.session_state.domains, max_people=max_people)
                        st.session_state.contacts = contacts
                        save_csv(_root("emails_output.csv"), contacts,
                                 ["company", "title", "name", "email"])
                        log(f"Extracted {len(contacts)} contacts", "success")
                        st.session_state.step = max(st.session_state.step, 3)
                        st.success(f"✅ {len(contacts)} contacts extracted")
                    except Exception as e:
                        log(f"Extraction error: {e}", "warning")
                        st.error(str(e))

        with col_load:
            if os.path.exists(_root("emails_output.csv")):
                if st.button("Load existing emails_output.csv", key="btn_load_contacts"):
                    st.session_state.contacts = load_csv(_root("emails_output.csv"))
                    log(f"Loaded {len(st.session_state.contacts)} existing contacts", "success")
                    st.session_state.step = max(st.session_state.step, 3)

        if st.session_state.contacts:
            st.dataframe(st.session_state.contacts, use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 3 — Crawl Websites
# ═══════════════════════════════════════════════════════════════════════════════
with st.expander("**Step 3 — Crawl Company Websites**", expanded=(st.session_state.step == 3)):
    st.markdown("<div class='step-title'><span class='step-badge'>3</span>Scrape site content for AI context</div>",
                unsafe_allow_html=True)

    if not st.session_state.domains:
        st.warning("Complete Step 1 first.")
    else:
        col_run, col_load = st.columns(2)
        with col_run:
            if st.button("▶ Run Crawler", key="btn_crawl"):
                from pipeline.crawler import crawl_domains
                with st.spinner("Crawling… this may take a while"):
                    log("Starting web crawl…")
                    try:
                        crawled = crawl_domains(st.session_state.domains)
                        st.session_state.crawled = crawled
                        rows = [{"domain": d, "scraped_content": c} for d, c in crawled.items()]
                        save_csv(_root("crawled_output.csv"), rows, ["domain", "scraped_content"])
                        log(f"Crawled {len(crawled)} sites", "success")
                        st.session_state.step = max(st.session_state.step, 4)
                        st.success(f"✅ {len(crawled)} sites crawled")
                    except Exception as e:
                        log(f"Crawl error: {e}", "warning")
                        st.error(str(e))

        with col_load:
            if os.path.exists(_root("crawled_output.csv")):
                if st.button("Load existing crawled_output.csv", key="btn_load_crawl"):
                    rows = load_csv(_root("crawled_output.csv"))
                    st.session_state.crawled = {r["domain"]: r.get("scraped_content", "") for r in rows}
                    log(f"Loaded {len(st.session_state.crawled)} crawled sites", "success")
                    st.session_state.step = max(st.session_state.step, 4)

        if st.session_state.crawled:
            preview_domain = st.selectbox("Preview domain", list(st.session_state.crawled.keys()),
                                          key="sel_preview")
            snippet = st.session_state.crawled[preview_domain][:800]
            st.markdown(f"<div class='email-preview'>{snippet}…</div>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 4 — Generate Emails
# ═══════════════════════════════════════════════════════════════════════════════
with st.expander("**Step 4 — Generate Personalized Emails**", expanded=(st.session_state.step == 4)):
    st.markdown("<div class='step-title'><span class='step-badge'>4</span>AI-draft outreach per contact</div>",
                unsafe_allow_html=True)

    st.info(f"🧪 **Test mode** — sends will go to `{TEST_EMAIL}`, not the real address.", icon="🔒")

    if not st.session_state.contacts:
        st.warning("Complete Steps 1–2 first.")
    else:
        from pipeline.email_generation import generate_email, generate_subject

        col_all, col_single = st.columns([1, 2])

        with col_all:
            if st.button("⚡ Generate All", key="btn_gen_all"):
                progress = st.progress(0, text="Generating…")
                total  = len(st.session_state.contacts)
                errors = []
                for i, c in enumerate(st.session_state.contacts):
                    company = c.get("company", "")
                    name    = c.get("name", "")
                    title   = c.get("title", "")
                    email   = c.get("email", "")
                    context = st.session_state.crawled.get(company, "No additional context available.")
                    try:
                        body    = generate_email(name=name, email=email, title=title,
                                                 content=context, company_name=company)
                        subject = generate_subject(company)
                        st.session_state.generated_emails[email] = {
                            "subject": subject, "body": body, "approved": False,
                            "name": name, "title": title, "company": company, "real_email": email,
                        }
                        log(f"Generated email for {name}", "success")
                    except Exception as e:
                        errors.append(f"{name}: {e}")
                        log(f"Failed for {name}: {e}", "warning")
                    progress.progress((i + 1) / total, text=f"{i+1}/{total}")

                if errors:
                    st.warning("Some failed:\n" + "\n".join(errors))
                else:
                    st.success(f"✅ {total} emails generated!")
                st.session_state.step = max(st.session_state.step, 5)

        with col_single:
            labels = [f"{c.get('name','?')} — {c.get('company','?')}"
                      for c in st.session_state.contacts]
            idx = st.selectbox("Generate for one contact", range(len(labels)),
                               format_func=lambda i: labels[i], key="sel_single")
            if st.button("Generate selected", key="btn_gen_single"):
                c       = st.session_state.contacts[idx]
                company = c.get("company", "")
                name    = c.get("name", "")
                title   = c.get("title", "")
                email   = c.get("email", "")
                context = st.session_state.crawled.get(company, "No additional context available.")
                with st.spinner(f"Generating for {name}…"):
                    try:
                        body    = generate_email(name=name, email=email, title=title,
                                                 content=context, company_name=company)
                        subject = generate_subject(company)
                        st.session_state.generated_emails[email] = {
                            "subject": subject, "body": body, "approved": False,
                            "name": name, "title": title, "company": company, "real_email": email,
                        }
                        log(f"Generated for {name}", "success")
                        st.success(f"✅ Draft ready for {name}")
                        st.session_state.step = max(st.session_state.step, 5)
                    except Exception as e:
                        st.error(str(e))

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 5 — Review & Send
# ═══════════════════════════════════════════════════════════════════════════════
with st.expander("**Step 5 — Review & Send**", expanded=(st.session_state.step == 5)):
    st.markdown("<div class='step-title'><span class='step-badge'>5</span>Approve drafts then send</div>",
                unsafe_allow_html=True)

    st.markdown(
        f"<div class='card'><span class='chip chip-warning'>🧪 Test Mode</span>"
        f"&nbsp; All emails will be delivered to <code>{TEST_EMAIL}</code>.</div>",
        unsafe_allow_html=True,
    )

    if not st.session_state.generated_emails:
        st.warning("No emails generated yet — complete Step 4 first.")
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

            # Persist inline edits back to state
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
                                svc = get_gmail_service()
                                msg_id = send_email(svc, to=TEST_EMAIL,
                                                    subject=new_subject, body=new_body)
                                log(f"Sent for {data['name']} → ID {msg_id}", "success")
                                st.success(f"✅ Sent! ID: {msg_id}")
                            except Exception as e:
                                log(f"Send failed: {e}", "warning")
                                st.error(str(e))

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
                    sent = 0
                    errs = []
                    for real_email, data in approved_map.items():
                        try:
                            msg_id = send_email(svc, to=TEST_EMAIL,
                                                subject=data["subject"], body=data["body"])
                            log(f"Bulk sent for {data['name']} → ID {msg_id}", "success")
                            sent += 1
                        except Exception as e:
                            errs.append(f"{data['name']}: {e}")
                            log(f"Bulk failed for {data['name']}: {e}", "warning")
                    if errs:
                        st.warning(f"Sent {sent}, failed {len(errs)}:\n" + "\n".join(errs))
                    else:
                        st.success(f"✅ {sent} emails sent to {TEST_EMAIL}!")
                except Exception as e:
                    st.error(f"Gmail init failed: {e}")
