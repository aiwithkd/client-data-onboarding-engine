# Client Data Onboarding Quality Engine

**Live App →** [client-data-onboarding-engine.streamlit.app](https://client-data-onboarding-engine.streamlit.app)

A production-inspired data quality and validation engine for client Excel files — built to catch schema issues, bad identifiers, missing fields, and business rule violations **before** they cause failures in a production load.

---

## Why This Exists

Anyone who has worked in financial data onboarding knows the problem: a client sends you 3 Excel sheets, each structured differently from the last, with column names that almost match what you expect, a few blank rows, some cells with dates formatted as `31-13-2020`, and an ISIN that's 11 characters instead of 12. You load it to production. Something breaks. You spend two days debugging.

This project automates the pre-load validation step. Instead of discovering data problems during or after a production import, you run this engine first — it tells you exactly what is wrong, where it is, how severe it is, and gives you a readiness score before anything touches a live system.

The design is directly inspired by real client onboarding work in fintech environments where a single bad row in a 10,000-row file can fail an entire batch load and trigger hours of rollback and investigation.

---

## What It Does

Upload any client Excel file (or use one of the 3 pre-built samples) and the engine:

1. **Ingests** all sheets, normalises column names, strips whitespace, drops blank rows
2. **Auto-detects** the client type by matching sheet names against a config registry
3. **Runs 12 quality checks** across every sheet
4. **Scores** the file from 0–100% with a readiness verdict: `READY`, `CONDITIONAL`, or `BLOCKED`
5. **Reports** every issue with severity (Critical / Warning / Info), exact row number, and a plain-English message
6. **Exports** a full QC report as a multi-tab Excel file for handoff or audit trail

---

## Quality Checks

| Check | Severity | What it catches |
|---|---|---|
| Missing required fields | CRITICAL | Null/blank values in columns that cannot be empty |
| Duplicate identifiers | CRITICAL | Same account ID, portfolio ID appearing more than once |
| ID format validation | CRITICAL | IDs that don't match the expected pattern (e.g. `HCM-12345`) |
| ISIN format & length | CRITICAL | Lowercase country code, wrong length, invalid characters |
| Invalid date values | CRITICAL | Dates that cannot be parsed in any known format |
| Settlement before trade date | CRITICAL | Settlement date earlier than trade date — impossible in real markets |
| Value below minimum | CRITICAL | Negative market values, prices below zero |
| Non-numeric amounts | CRITICAL | Text in columns that should always be numbers |
| Value above expected maximum | WARNING | Suspiciously large values — likely data entry errors (e.g. extra zeros) |
| Invalid currency codes | WARNING | Currency not in the allowed list for that client |
| Negative quantities | WARNING | Short positions or data errors — flagged for manual review |
| Unexpected columns | INFO | Columns present in the file but not in the expected schema |

---

## Readiness Scoring

The readiness score is calculated per file, not per check. It starts at 100 and deducts points based on how many issues were found relative to total records:

- **Critical issues** deduct 3× more than warnings
- **Warnings** deduct 1×
- **Info flags** deduct 0.2×

This means a 1,000-row file with 5 critical issues scores very differently from a 50-row file with the same 5 issues — which is intentional. Scale matters in data quality assessment.

| Score | Status | Meaning |
|---|---|---|
| 90–100% | READY | Safe to load — minor or no issues |
| 70–89% | CONDITIONAL | Review warnings before loading |
| Below 70% | BLOCKED | Critical issues must be resolved first |

---

## Architecture

```
client-data-onboarding-engine/
├── app.py                    # Streamlit UI — entry point
├── src/
│   ├── config.py             # Client config registry — schema + business rules per client
│   ├── ingest.py             # Excel reader — normalises sheets, detects client type
│   ├── quality_checks.py     # All 12 QC checks + readiness scorer
│   └── generate_data.py      # Generates realistic messy sample files for all 3 clients
├── sample_data/
│   ├── client_horizon_capital.xlsx
│   ├── client_meridian_wealth.xlsx
│   └── client_bluerock_advisors.xlsx
├── requirements.txt
└── .gitignore
```

### Key design decisions

**Config-driven, not hardcoded.** Every client has a config block in `config.py` that defines expected columns, required fields, ID patterns, value ranges, and currency rules. Adding a new client requires zero changes to any check logic — only a new config block. This mirrors how real onboarding pipelines are built: the rules change per client, the engine doesn't.

**Checks are independent functions.** Each quality check is a standalone function that takes a DataFrame and returns a list of findings. They don't share state, don't call each other, and can be run in any order. This makes it easy to add, remove, or adjust a single check without touching anything else.

**Severity is intentional.** Not every issue is a blocker. A missing optional column is INFO. An account ID with the wrong format is CRITICAL. The scoring system reflects this — a file can have 20 INFO flags and still be READY, but 3 CRITICAL issues will BLOCK it regardless.

**Upload mode for any file.** The engine isn't locked to the 3 sample clients. Any Excel file can be uploaded — the ingest layer normalises it, the auto-detect logic matches it to the closest config, and all applicable checks run. For unknown files, it falls back to ISIN checks, date checks, and numeric checks which are universal.

---

## Sample Clients — What Issues They Have

The three sample files are generated with intentional, realistic data problems that mirror what actually shows up in client onboarding:

**Horizon Capital Management** (`client_horizon_capital.xlsx`)
- Account IDs with letter O instead of zero (`HCM-1002O`)
- Lowercase ISIN country codes (`us...` instead of `US...`)
- An impossible date: `31-13-2020`
- Negative market values from sign-flip errors
- Missing required fields scattered across accounts and valuations

**Meridian Wealth Advisors** (`client_meridian_wealth.xlsx`)
- Settlement dates before trade dates (the most common real-world transaction error)
- Invalid currency codes from non-standard source systems
- Client references in wrong format
- Missing required fields across all three sheets

**Bluerock Advisory Group** (`client_bluerock_advisors.xlsx`)
- Portfolio IDs with formatting issues (`BR1003` instead of `BR-EQ-1003`)
- Market values inflated by a factor of 10,000 (extra zeros from copy-paste)
- Inconsistent boolean representation (`True`, `Yes`, `yes`, `1` all in the same column)
- Missing SEDOL identifiers (common — SEDOL coverage is often incomplete)

---

## Running Locally

```bash
git clone https://github.com/aiwithkd/client-data-onboarding-engine.git
cd client-data-onboarding-engine

pip install -r requirements.txt

# Generate the sample data files
python src/generate_data.py

# Launch the app
streamlit run app.py
```

Open `http://localhost:8501` in your browser.

---

## Challenges Faced During Implementation

### 1. ISIN used as a row identifier — but it isn't one

**Problem:** The initial config used `isin` as the `id_column` for holdings and positions sheets, triggering the duplicate ID check on every file. ISINs are security identifiers, not row identifiers — multiple clients can hold the same security, and the same portfolio can have the same ISIN across different dates. This caused 71 false DUPLICATE_ID findings on Meridian Wealth alone.

**Resolution:** Separated the concept of "ID format check" (is this ISIN valid?) from "uniqueness check" (is this row unique?). The `id_column` in config now only applies to entities that are genuinely unique per row — account IDs, client references, portfolio IDs. ISIN validity is checked separately by `check_isin_format()` which runs on any column named `isin` regardless of config, without treating it as a uniqueness constraint.

---

### 2. Non-numeric check firing on date and name columns

**Problem:** The `check_non_numeric_amounts()` function looked for columns containing words like `value`, `amount`, `cost` and tried to parse them as numbers. Columns like `market_value_date` or `cost_center_name` matched this heuristic and generated hundreds of false CRITICAL findings.

**Resolution:** Added an exclusion list of date/identifier hints (`date`, `dt`, `time`, `id`, `ref`, `name`, `type`, `code`) — if a column name contains any of these, it's skipped by the numeric check even if it also contains a numeric keyword. The heuristic went from purely additive (any match = check it) to subtractive (match + no exclusion = check it).

---

### 3. None values being treated as duplicate IDs

**Problem:** When `client_ref` was intentionally left null in some rows (to simulate missing data), pandas treated all `None` values as equal — so 15 rows with null client refs were being flagged as 15 duplicate IDs of each other. This was technically correct pandas behaviour but wrong domain logic.

**Resolution:** Added an explicit filter before the duplicate check: only run it on rows where the ID column is non-null, non-empty string, and not the literal string `"none"`. Nulls are already caught by `check_missing_required()` — they don't need to also trigger `check_duplicate_ids()`.

---

### 4. Python 3.9 type hint incompatibility

**Problem:** The ingest module used `dict[str, pd.DataFrame]` and `str | None` type hints (Python 3.10+ syntax), which threw `TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'` on Python 3.9.

**Resolution:** Replaced union type hints with bare `dict` and removed the return type annotations from functions that used the new syntax. The app targets Python 3.9+ (the most widely available version) so the code is written to that baseline.

---

### 5. Streamlit app pathing for `src/` modules

**Problem:** Running `streamlit run app.py` from the project root failed to resolve imports from the `src/` directory — `from ingest import load_excel` raised `ModuleNotFoundError`.

**Resolution:** Added `sys.path.insert(0, str(Path(__file__).parent / "src"))` at the top of `app.py` before any local imports. This works both locally and on Streamlit Community Cloud because it's relative to the file location, not the working directory.

---

## Future Scope

This engine is intentionally built as a standalone local tool — no external APIs, no cloud services, no authentication required. Anyone can clone it and run it in under 2 minutes.

Natural extensions that the architecture already supports:

- **Cloud pipeline integration** — the check engine (`quality_checks.py`) is fully decoupled from the UI. It can be imported and run inside a Databricks notebook, AWS Glue job, or any orchestration layer with no changes.
- **LLM-powered issue explanations** — findings are plain dicts. An LLM layer (Claude API, Gemini, local model) could be added on top to explain each issue in plain English and suggest a fix — without changing the check logic at all.
- **Database output** — swap `report.json` for a write to PostgreSQL or Delta Lake for historical QC tracking across client loads.
- **Custom rule builder** — extend the config schema to support user-defined regex patterns and value ranges via the Streamlit UI, without touching Python.

---

## Tech Stack

| Layer | Technology |
|---|---|
| UI | Streamlit |
| Data processing | Python, Pandas, NumPy |
| Excel read/write | OpenPyXL |
| String matching | Python `re` (stdlib) |
| Hosting | Streamlit Community Cloud |
| External APIs | None |
| Cloud services | None |
