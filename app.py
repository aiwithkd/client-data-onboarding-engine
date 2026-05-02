"""
Client Data Onboarding Quality Engine
Streamlit app — run with: streamlit run app.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import streamlit as st
import pandas as pd
from io import BytesIO

from ingest import load_excel, detect_client_type
from quality_checks import (
    run_all_checks, compute_readiness_score,
    check_isin_format, check_date_columns,
    check_negative_quantities, check_non_numeric_amounts,
)
from config import CLIENT_CONFIGS

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Client Data Onboarding Engine",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Styling ────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main { background-color: #f5f7fa; }
    .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }

    .metric-card {
        background: white;
        border-radius: 12px;
        padding: 20px 24px;
        border: 1px solid #e2e6ed;
        box-shadow: 0 1px 3px rgba(0,0,0,.06);
        text-align: center;
    }
    .metric-label {
        font-size: 0.72rem;
        font-weight: 600;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: .05em;
        margin-bottom: 6px;
    }
    .metric-value {
        font-size: 2rem;
        font-weight: 800;
        letter-spacing: -.03em;
        line-height: 1;
    }
    .score-ready      { color: #16a34a; }
    .score-conditional{ color: #d97706; }
    .score-blocked    { color: #dc2626; }

    .badge-critical { background:#fef2f2; color:#dc2626; border:1px solid #fecaca; padding:2px 10px; border-radius:20px; font-size:0.72rem; font-weight:600; }
    .badge-warning  { background:#fffbeb; color:#d97706; border:1px solid #fde68a; padding:2px 10px; border-radius:20px; font-size:0.72rem; font-weight:600; }
    .badge-info     { background:#eff6ff; color:#2563eb; border:1px solid #bfdbfe; padding:2px 10px; border-radius:20px; font-size:0.72rem; font-weight:600; }

    .status-ready       { background:#dcfce7; color:#15803d; padding:6px 18px; border-radius:20px; font-weight:700; font-size:0.85rem; display:inline-block; }
    .status-conditional { background:#fef9c3; color:#854d0e; padding:6px 18px; border-radius:20px; font-weight:700; font-size:0.85rem; display:inline-block; }
    .status-blocked     { background:#fee2e2; color:#991b1b; padding:6px 18px; border-radius:20px; font-weight:700; font-size:0.85rem; display:inline-block; }

    .section-header {
        font-size: 1rem;
        font-weight: 700;
        color: #0f172a;
        margin: 1.5rem 0 0.75rem;
        padding-bottom: 6px;
        border-bottom: 2px solid #e2e6ed;
    }

    div[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }
    .stTabs [data-baseweb="tab-list"] { gap: 4px; }
    .stTabs [data-baseweb="tab"] { border-radius: 8px 8px 0 0; font-weight: 500; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ────────────────────────────────────────────────────────────────────

def severity_badge(sev):
    cls = {"CRITICAL": "badge-critical", "WARNING": "badge-warning", "INFO": "badge-info"}.get(sev, "badge-info")
    return f'<span class="{cls}">{sev}</span>'


def status_badge(status):
    cls = {"READY": "status-ready", "CONDITIONAL": "status-conditional", "BLOCKED": "status-blocked"}.get(status, "status-blocked")
    icons = {"READY": "✅ READY TO LOAD", "CONDITIONAL": "⚠️ CONDITIONAL", "BLOCKED": "🚫 BLOCKED"}
    return f'<span class="{cls}">{icons.get(status, status)}</span>'


def score_color_class(status):
    return {"READY": "score-ready", "CONDITIONAL": "score-conditional", "BLOCKED": "score-blocked"}.get(status, "score-blocked")


def run_qc(file_source, client_key_override=None):
    try:
        sheets = load_excel(file_source)
    except Exception as e:
        return None, None, None, None, str(e)

    if not sheets:
        return None, None, None, None, "File loaded but contained no readable sheets."

    client_key = client_key_override or detect_client_type(sheets, CLIENT_CONFIGS)

    if not client_key:
        # Unknown file — run universal checks only (ISIN, dates, numerics, nulls)
        findings = []
        for sheet_name, df in sheets.items():
            findings += check_isin_format(df, sheet_name)
            findings += check_date_columns(df, sheet_name, [c for c in df.columns if any(h in c for h in ["date", "dt"])])
            findings += check_negative_quantities(df, sheet_name)
            findings += check_non_numeric_amounts(df, sheet_name)
        total_records = sum(len(df) for df in sheets.values())
        scorecard = compute_readiness_score(findings, total_records)
        return sheets, None, findings, scorecard, None

    config   = CLIENT_CONFIGS[client_key]
    findings = run_all_checks(sheets, config)
    total_records = sum(len(df) for df in sheets.values())
    scorecard = compute_readiness_score(findings, total_records)

    return sheets, client_key, findings, scorecard, None


def findings_to_df(findings):
    if not findings:
        return pd.DataFrame()
    df = pd.DataFrame(findings)
    df["row"] = df["row"].fillna("—").astype(str).str.replace(".0", "", regex=False)
    return df[["severity", "sheet", "column", "row", "check_type", "message", "value"]]


# ── Sidebar ────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 📋 Onboarding Engine")
    st.markdown("---")

    mode = st.radio(
        "Data source",
        ["Use sample client file", "Upload your own file"],
        index=0,
    )

    if mode == "Use sample client file":
        sample_map = {
            "Horizon Capital Management":  ("client_horizon_capital.xlsx",  "horizon_capital"),
            "Meridian Wealth Advisors":    ("client_meridian_wealth.xlsx",   "meridian_wealth"),
            "Bluerock Advisory Group":     ("client_bluerock_advisors.xlsx", "bluerock_advisors"),
        }
        selected = st.selectbox("Select client", list(sample_map.keys()))
        file_name, client_key_hint = sample_map[selected]
        sample_path = Path(__file__).parent / "sample_data" / file_name

        run_btn = st.button("▶  Run Quality Check", type="primary", use_container_width=True)
        uploaded_file = None

    else:
        st.markdown("""
**How to use upload mode**

Upload any `.xlsx` file with one or more sheets. The engine will:
- Auto-detect if it matches a known client format
- Run all applicable checks if matched
- Run universal checks (ISIN validity, date formats, numeric fields, negative values) on any file

**Your file doesn't need to match any specific format** — the engine adapts to what it finds.

> ⚠️ Do not upload files with sensitive or real client data. Use anonymised or test data only.
""")
        uploaded_file = st.file_uploader(
            "Upload Excel file (.xlsx)",
            type=["xlsx"],
            help="Multi-sheet Excel files work best. Password-protected files are not supported.",
        )
        client_key_hint = None
        run_btn = st.button("▶  Run Quality Check", type="primary", use_container_width=True,
                            disabled=(uploaded_file is None))

    st.markdown("---")
    st.markdown("""
**Checks performed**
- Missing required fields
- Duplicate identifiers
- ID format validation
- ISIN format & length
- Date parsing & future dates
- Settlement before trade date
- Out-of-range values
- Invalid currencies
- Negative quantities
- Non-numeric amounts
- Schema drift detection
""")
    st.markdown("---")
    st.caption("Built by [Kunal Deokar](https://github.com/aiwithkd) · 100% local, no APIs")


# ── Main ───────────────────────────────────────────────────────────────────────

st.markdown("# Client Data Onboarding Quality Engine")
st.markdown("Validate client Excel files before production load — catch schema issues, bad identifiers, missing fields, and business rule violations before they cause failures downstream.")

if not run_btn:
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-label">Supported checks</div>
            <div class="metric-value" style="color:#2563eb;">12</div>
            <div style="font-size:0.75rem;color:#64748b;margin-top:4px;">across all sheet types</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-label">Client configs</div>
            <div class="metric-value" style="color:#7c3aed;">3</div>
            <div style="font-size:0.75rem;color:#64748b;margin-top:4px;">pre-loaded + custom upload</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-label">External dependencies</div>
            <div class="metric-value" style="color:#16a34a;">0</div>
            <div style="font-size:0.75rem;color:#64748b;margin-top:4px;">runs fully offline</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.info("👈 Select a sample client or upload your own Excel file, then click **Run Quality Check**.")
    st.stop()


# ── Run QC ─────────────────────────────────────────────────────────────────────

with st.spinner("Running quality checks..."):
    if mode == "Use sample client file":
        if not sample_path.exists():
            st.error(f"Sample file not found: `{sample_path}`. Run `python src/generate_data.py` first.")
            st.stop()
        sheets, client_key, findings, scorecard, err = run_qc(sample_path, client_key_hint)
    else:
        file_bytes = BytesIO(uploaded_file.read())
        sheets, client_key, findings, scorecard, err = run_qc(file_bytes)

if sheets is None:
    st.error("Could not read the file.")
    st.markdown("""
**Common reasons this happens:**
- The file is password-protected — remove the password before uploading
- The file is corrupted or not a real `.xlsx` file (e.g. a `.csv` renamed to `.xlsx`)
- The file has no data — all sheets are empty
- The file uses a very old Excel format (`.xls`) — save it as `.xlsx` first

If you're testing with a real file, try opening it in Excel, doing **File → Save As → .xlsx**, and uploading again.
""")
    if err:
        with st.expander("Technical error details"):
            st.code(err)
    st.stop()

total_records = sum(len(df) for df in sheets.values())

if client_key is None:
    st.markdown("---")
    st.info("""
**File loaded successfully — running universal checks**

This file doesn't match any of the 3 pre-configured client formats, so full schema validation is skipped.
Universal checks are still running: ISIN format, date validity, negative quantities, and non-numeric fields.

To get full validation, your file's sheet names should match one of:
- `accounts`, `securities`, `valuations` → Horizon Capital format
- `clients`, `holdings`, `transactions` → Meridian Wealth format
- `portfolio`, `positions`, `cashflows` → Bluerock Advisors format
""")
    hcol1, hcol2 = st.columns([3, 1])
    with hcol1:
        st.markdown(f"### Uploaded File")
        st.markdown(f"**{total_records:,} total records** across **{len(sheets)} sheets**: {', '.join(f'`{s}`' for s in sheets)}")
    with hcol2:
        if scorecard:
            st.markdown(f"<br>{status_badge(scorecard['status'])}", unsafe_allow_html=True)

    if scorecard:
        st.markdown("---")
        k1, k2, k3, k4 = st.columns(4)
        with k1:
            cls = score_color_class(scorecard["status"])
            st.markdown(f'<div class="metric-card"><div class="metric-label">Readiness Score</div><div class="metric-value {cls}">{scorecard["score"]}%</div></div>', unsafe_allow_html=True)
        with k2:
            st.markdown(f'<div class="metric-card"><div class="metric-label">Total Issues</div><div class="metric-value">{scorecard["total"]}</div></div>', unsafe_allow_html=True)
        with k3:
            st.markdown(f'<div class="metric-card"><div class="metric-label">Critical</div><div class="metric-value score-blocked">{scorecard["critical"]}</div></div>', unsafe_allow_html=True)
        with k4:
            st.markdown(f'<div class="metric-card"><div class="metric-label">Warnings</div><div class="metric-value score-conditional">{scorecard["warnings"]}</div></div>', unsafe_allow_html=True)
        st.markdown("")

    if findings:
        findings_df_u = findings_to_df(findings)
        st.markdown("#### Issues Found")
        st.dataframe(
            findings_df_u.style.applymap(
                lambda v: "background-color:#fef2f2;color:#dc2626;font-weight:600" if v == "CRITICAL"
                     else "background-color:#fffbeb;color:#d97706;font-weight:600" if v == "WARNING"
                     else "background-color:#eff6ff;color:#2563eb;font-weight:600",
                subset=["severity"]
            ),
            use_container_width=True, height=400
        )
    else:
        st.success("No issues detected on universal checks.")

    st.markdown("#### Sheet Preview")
    sheet_choice_u = st.selectbox("Select sheet", list(sheets.keys()))
    st.dataframe(sheets[sheet_choice_u], use_container_width=True, height=400)
    st.stop()

config = CLIENT_CONFIGS[client_key]

# ── Header row ─────────────────────────────────────────────────────────────────
display_name = config['display_name'] if mode == "Use sample client file" else f"{config['display_name']} (auto-detected)"
st.markdown("---")
hcol1, hcol2 = st.columns([3, 1])
with hcol1:
    st.markdown(f"### {display_name}")
    st.markdown(f"**{total_records:,} total records** across **{len(sheets)} sheets**: {', '.join(f'`{s}`' for s in sheets)}")
with hcol2:
    st.markdown(f"<br>{status_badge(scorecard['status'])}", unsafe_allow_html=True)

# ── Scorecard KPIs ─────────────────────────────────────────────────────────────
st.markdown("---")
k1, k2, k3, k4, k5 = st.columns(5)

with k1:
    cls = score_color_class(scorecard["status"])
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Readiness Score</div>
        <div class="metric-value {cls}">{scorecard['score']}%</div>
    </div>""", unsafe_allow_html=True)
with k2:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Total Issues</div>
        <div class="metric-value" style="color:#0f172a;">{scorecard['total']}</div>
    </div>""", unsafe_allow_html=True)
with k3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Critical</div>
        <div class="metric-value score-blocked">{scorecard['critical']}</div>
    </div>""", unsafe_allow_html=True)
with k4:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Warnings</div>
        <div class="metric-value score-conditional">{scorecard['warnings']}</div>
    </div>""", unsafe_allow_html=True)
with k5:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Info</div>
        <div class="metric-value" style="color:#2563eb;">{scorecard['info']}</div>
    </div>""", unsafe_allow_html=True)

st.markdown("")

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab_issues, tab_by_sheet, tab_data, tab_export = st.tabs([
    f"🔍 All Issues ({scorecard['total']})",
    "📊 Issues by Sheet",
    "📄 Data Preview",
    "⬇️ Export Report",
])

# ── Tab 1: All issues ──────────────────────────────────────────────────────────
with tab_issues:
    findings_df = findings_to_df(findings)

    if findings_df.empty:
        st.success("No issues found. This file looks clean.")
    else:
        # Filters
        fcol1, fcol2, fcol3 = st.columns(3)
        with fcol1:
            sev_filter = st.multiselect("Severity", ["CRITICAL", "WARNING", "INFO"],
                                         default=["CRITICAL", "WARNING", "INFO"])
        with fcol2:
            sheet_filter = st.multiselect("Sheet", sorted(findings_df["sheet"].dropna().unique()),
                                           default=sorted(findings_df["sheet"].dropna().unique()))
        with fcol3:
            check_filter = st.multiselect("Check type", sorted(findings_df["check_type"].unique()),
                                           default=sorted(findings_df["check_type"].unique()))

        filtered = findings_df[
            findings_df["severity"].isin(sev_filter) &
            findings_df["sheet"].isin(sheet_filter) &
            findings_df["check_type"].isin(check_filter)
        ].reset_index(drop=True)

        st.markdown(f"Showing **{len(filtered)}** of {len(findings_df)} issues")

        def color_severity(val):
            colors = {"CRITICAL": "background-color:#fef2f2;color:#dc2626;font-weight:600",
                      "WARNING":  "background-color:#fffbeb;color:#d97706;font-weight:600",
                      "INFO":     "background-color:#eff6ff;color:#2563eb;font-weight:600"}
            return colors.get(val, "")

        styled = filtered.style.applymap(color_severity, subset=["severity"])
        st.dataframe(styled, use_container_width=True, height=450)


# ── Tab 2: Issues by sheet ─────────────────────────────────────────────────────
with tab_by_sheet:
    if not findings:
        st.success("No issues found.")
    else:
        findings_df2 = findings_to_df(findings)
        for sheet_name in sheets:
            sheet_findings = findings_df2[findings_df2["sheet"] == sheet_name]
            n_rows = len(sheets[sheet_name])
            crits  = len(sheet_findings[sheet_findings["severity"] == "CRITICAL"])
            warns  = len(sheet_findings[sheet_findings["severity"] == "WARNING"])
            infos  = len(sheet_findings[sheet_findings["severity"] == "INFO"])

            with st.expander(f"**{sheet_name}** — {n_rows} rows · {len(sheet_findings)} issues  (🔴 {crits} · 🟡 {warns} · 🔵 {infos})", expanded=(crits > 0)):
                if sheet_findings.empty:
                    st.success("No issues in this sheet.")
                else:
                    st.dataframe(
                        sheet_findings.style.applymap(
                            lambda v: "background-color:#fef2f2;color:#dc2626;font-weight:600" if v == "CRITICAL"
                                 else "background-color:#fffbeb;color:#d97706;font-weight:600" if v == "WARNING"
                                 else "background-color:#eff6ff;color:#2563eb;font-weight:600",
                            subset=["severity"]
                        ),
                        use_container_width=True,
                        height=300,
                    )


# ── Tab 3: Data preview ────────────────────────────────────────────────────────
with tab_data:
    sheet_choice = st.selectbox("Select sheet to preview", list(sheets.keys()))
    df_preview   = sheets[sheet_choice]
    st.markdown(f"**{len(df_preview)} rows · {len(df_preview.columns)} columns**")
    st.dataframe(df_preview, use_container_width=True, height=450)


# ── Tab 4: Export ──────────────────────────────────────────────────────────────
with tab_export:
    st.markdown("### Download QC Report")
    st.markdown("Export all findings as Excel — one sheet per severity level, plus a summary tab.")

    if findings:
        findings_df3 = findings_to_df(findings)

        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            # Summary sheet
            summary_data = {
                "Metric": ["Client", "Total Records", "Readiness Score", "Status",
                           "Critical Issues", "Warnings", "Info", "Report Generated"],
                "Value":  [config["display_name"], total_records, f"{scorecard['score']}%",
                           scorecard["status"], scorecard["critical"], scorecard["warnings"],
                           scorecard["info"], pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")],
            }
            pd.DataFrame(summary_data).to_excel(writer, sheet_name="Summary", index=False)

            # All findings
            findings_df3.to_excel(writer, sheet_name="All Issues", index=False)

            # Per severity
            for sev in ["CRITICAL", "WARNING", "INFO"]:
                sub = findings_df3[findings_df3["severity"] == sev]
                if not sub.empty:
                    sub.to_excel(writer, sheet_name=sev.title(), index=False)

            # Per sheet
            for sheet_name in sheets:
                sub = findings_df3[findings_df3["sheet"] == sheet_name]
                if not sub.empty:
                    safe_name = sheet_name[:28]
                    sub.to_excel(writer, sheet_name=f"Sheet_{safe_name}", index=False)

        output.seek(0)
        fname = f"qc_report_{client_key}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.xlsx"
        st.download_button(
            label="⬇️  Download QC Report (.xlsx)",
            data=output,
            file_name=fname,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
        )
        st.caption(f"Report will include: Summary · All Issues · Critical · Warning · Info · per-sheet tabs")
    else:
        st.success("No issues found — nothing to export. File is clean.")
