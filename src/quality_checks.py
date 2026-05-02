"""
Quality check engine.
Each check returns a list of Finding dicts:
  {
    sheet, column, row_index, severity, check_type, message, value
  }

Severity levels: CRITICAL | WARNING | INFO
"""

import re
import pandas as pd
from datetime import datetime


SEVERITY_CRITICAL = "CRITICAL"
SEVERITY_WARNING  = "WARNING"
SEVERITY_INFO     = "INFO"

ISIN_PATTERN  = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}\d$")
DATE_FORMATS  = ["%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y", "%d/%m/%Y", "%d-%b-%Y", "%Y%m%d"]


def _finding(sheet, col, row, severity, check_type, message, value=None):
    return {
        "sheet":      sheet,
        "column":     col,
        "row":        row,
        "severity":   severity,
        "check_type": check_type,
        "message":    message,
        "value":      str(value) if value is not None else "",
    }


def _try_parse_date(val):
    if pd.isna(val) or val == "":
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(str(val).strip(), fmt)
        except ValueError:
            continue
    return False  # unparseable


# ── Individual checks ──────────────────────────────────────────────────────────

def check_missing_required(df, sheet_name, required_cols):
    findings = []
    for col in required_cols:
        if col not in df.columns:
            findings.append(_finding(sheet_name, col, None, SEVERITY_CRITICAL,
                "MISSING_COLUMN", f"Required column '{col}' not found in sheet"))
            continue
        null_rows = df[df[col].isna() | (df[col].astype(str).str.strip() == "")].index.tolist()
        for row in null_rows:
            findings.append(_finding(sheet_name, col, int(row) + 2, SEVERITY_CRITICAL,
                "NULL_REQUIRED", f"Required field is empty", df[col].iloc[row] if row < len(df) else None))
    return findings


def check_duplicate_ids(df, sheet_name, id_col):
    findings = []
    if id_col not in df.columns:
        return findings
    valid = df[id_col].notna() & (df[id_col].astype(str).str.strip() != "") & (df[id_col].astype(str).str.lower() != "none")
    dupes = df[valid & df[id_col].duplicated(keep=False)]
    seen  = set()
    for row, val in zip(dupes.index, dupes[id_col]):
        if val not in seen:
            count = (df[id_col] == val).sum()
            findings.append(_finding(sheet_name, id_col, int(row) + 2, SEVERITY_CRITICAL,
                "DUPLICATE_ID", f"Duplicate identifier found ({count} occurrences)", val))
            seen.add(val)
    return findings


def check_id_format(df, sheet_name, id_col, pattern_str):
    findings = []
    if id_col not in df.columns or not pattern_str:
        return findings
    pattern = re.compile(pattern_str)
    for row, val in df[id_col].items():
        if pd.isna(val) or str(val).strip() == "":
            continue
        if not pattern.match(str(val).strip()):
            findings.append(_finding(sheet_name, id_col, int(row) + 2, SEVERITY_CRITICAL,
                "INVALID_ID_FORMAT", f"ID does not match expected format ({pattern_str})", val))
    return findings


def check_isin_format(df, sheet_name):
    findings = []
    isin_cols = [c for c in df.columns if "isin" in c.lower()]
    for col in isin_cols:
        for row, val in df[col].items():
            if pd.isna(val) or str(val).strip() == "":
                continue
            v = str(val).strip()
            if not ISIN_PATTERN.match(v):
                # classify the specific error
                if v != v.upper():
                    msg = "ISIN contains lowercase characters"
                elif len(v) != 12:
                    msg = f"ISIN length is {len(v)}, expected 12"
                else:
                    msg = "ISIN format invalid"
                findings.append(_finding(sheet_name, col, int(row) + 2, SEVERITY_CRITICAL,
                    "INVALID_ISIN", msg, val))
    return findings


def check_date_columns(df, sheet_name, date_cols):
    findings = []
    for col in date_cols:
        if col not in df.columns:
            continue
        for row, val in df[col].items():
            if pd.isna(val) or str(val).strip() == "":
                continue
            result = _try_parse_date(val)
            if result is False:
                findings.append(_finding(sheet_name, col, int(row) + 2, SEVERITY_CRITICAL,
                    "INVALID_DATE", f"Cannot parse date value", val))
            elif result and result > datetime.now():
                findings.append(_finding(sheet_name, col, int(row) + 2, SEVERITY_WARNING,
                    "FUTURE_DATE", f"Date is in the future", val))
    return findings


def check_settle_before_trade(df, sheet_name):
    findings = []
    if "trade_date" not in df.columns or "settle_date" not in df.columns:
        return findings
    for row in df.index:
        t = _try_parse_date(df["trade_date"].iloc[row])
        s = _try_parse_date(df["settle_date"].iloc[row])
        if t and s and isinstance(t, datetime) and isinstance(s, datetime):
            if s < t:
                findings.append(_finding(sheet_name, "settle_date", int(row) + 2, SEVERITY_CRITICAL,
                    "SETTLE_BEFORE_TRADE", "Settlement date is before trade date",
                    f"{df['settle_date'].iloc[row]} < {df['trade_date'].iloc[row]}"))
    return findings


def check_value_ranges(df, sheet_name, range_rules):
    findings = []
    for col, (min_val, max_val) in range_rules.items():
        if col not in df.columns:
            continue
        numeric = pd.to_numeric(df[col], errors="coerce")
        for row, val in numeric.items():
            if pd.isna(val):
                continue
            if val < min_val:
                findings.append(_finding(sheet_name, col, int(row) + 2, SEVERITY_CRITICAL,
                    "VALUE_BELOW_MIN", f"Value {val} is below minimum ({min_val})", val))
            elif val > max_val:
                findings.append(_finding(sheet_name, col, int(row) + 2, SEVERITY_WARNING,
                    "VALUE_ABOVE_MAX", f"Value {val} exceeds expected maximum ({max_val:,})", val))
    return findings


def check_currency(df, sheet_name, currency_col, valid_currencies):
    findings = []
    if not currency_col or currency_col not in df.columns or not valid_currencies:
        return findings
    for row, val in df[currency_col].items():
        if pd.isna(val) or str(val).strip() == "":
            continue
        if str(val).strip().upper() not in valid_currencies:
            findings.append(_finding(sheet_name, currency_col, int(row) + 2, SEVERITY_WARNING,
                "INVALID_CURRENCY", f"'{val}' is not in allowed currency list {valid_currencies}", val))
    return findings


def check_unexpected_columns(df, sheet_name, expected_cols):
    findings = []
    extra = set(df.columns) - set(expected_cols)
    for col in extra:
        findings.append(_finding(sheet_name, col, None, SEVERITY_INFO,
            "UNEXPECTED_COLUMN", f"Column '{col}' not in expected schema — verify if intentional"))
    return findings


def check_missing_expected_columns(df, sheet_name, expected_cols):
    findings = []
    missing = set(expected_cols) - set(df.columns)
    for col in missing:
        findings.append(_finding(sheet_name, col, None, SEVERITY_WARNING,
            "MISSING_EXPECTED_COLUMN", f"Expected column '{col}' not found in sheet"))
    return findings


def check_negative_quantities(df, sheet_name):
    findings = []
    qty_cols = [c for c in df.columns if c in ("quantity", "qty", "units", "shares")]
    for col in qty_cols:
        numeric = pd.to_numeric(df[col], errors="coerce")
        neg_rows = numeric[numeric < 0].index.tolist()
        for row in neg_rows:
            findings.append(_finding(sheet_name, col, int(row) + 2, SEVERITY_WARNING,
                "NEGATIVE_QUANTITY", f"Negative quantity — verify if short position or data error",
                numeric.iloc[row]))
    return findings


def check_non_numeric_amounts(df, sheet_name):
    findings = []
    numeric_hints = ["value", "amount", "price", "val", "cost", "qty", "quantity", "mkt"]
    # Exclude columns that are likely dates or identifiers
    date_hints = ["date", "dt", "time", "id", "ref", "code", "name", "type", "currency", "ccy", "status"]
    for col in df.columns:
        if any(h in col for h in numeric_hints) and not any(d in col for d in date_hints):
            coerced = pd.to_numeric(df[col], errors="coerce")
            bad_rows = df[coerced.isna() & df[col].notna() & (df[col].astype(str).str.strip() != "")].index
            for row in bad_rows:
                findings.append(_finding(sheet_name, col, int(row) + 2, SEVERITY_CRITICAL,
                    "NON_NUMERIC_VALUE", f"Expected numeric value but got non-numeric data",
                    df[col].iloc[row]))
    return findings


# ── Master runner ──────────────────────────────────────────────────────────────

def run_all_checks(sheets: dict, client_config: dict) -> list[dict]:
    all_findings = []

    for sheet_name, df in sheets.items():
        sheet_cfg = client_config["sheets"].get(sheet_name)
        biz_rules = client_config["business_rules"]

        if sheet_cfg is None:
            all_findings.append(_finding(sheet_name, None, None, SEVERITY_INFO,
                "UNKNOWN_SHEET", f"Sheet '{sheet_name}' not in client config — skipping structured checks"))
            continue

        all_findings += check_missing_expected_columns(df, sheet_name, sheet_cfg["expected_columns"])
        all_findings += check_unexpected_columns(df, sheet_name, sheet_cfg["expected_columns"])
        all_findings += check_missing_required(df, sheet_name, sheet_cfg["required"])
        all_findings += check_duplicate_ids(df, sheet_name, sheet_cfg["id_column"]) if sheet_cfg["id_column"] else []
        all_findings += check_id_format(df, sheet_name, sheet_cfg["id_column"], sheet_cfg["id_format"])
        all_findings += check_isin_format(df, sheet_name)
        all_findings += check_date_columns(df, sheet_name, biz_rules.get("date_columns", []))
        all_findings += check_settle_before_trade(df, sheet_name)
        all_findings += check_value_ranges(df, sheet_name, biz_rules.get("value_range", {}))
        all_findings += check_currency(df, sheet_name, biz_rules.get("currency_column"), biz_rules.get("valid_currencies", []))
        all_findings += check_negative_quantities(df, sheet_name)
        all_findings += check_non_numeric_amounts(df, sheet_name)

    return all_findings


def compute_readiness_score(findings: list[dict], total_records: int) -> dict:
    critical = sum(1 for f in findings if f["severity"] == SEVERITY_CRITICAL)
    warnings = sum(1 for f in findings if f["severity"] == SEVERITY_WARNING)
    info     = sum(1 for f in findings if f["severity"] == SEVERITY_INFO)

    # Score: start at 100, deduct per issue weighted by severity
    deduction = (critical * 3.0) + (warnings * 1.0) + (info * 0.2)
    base      = max(total_records, 1)
    score     = max(0, round(100 - (deduction / base * 100), 1))

    if score >= 90:
        status = "READY"
    elif score >= 70:
        status = "CONDITIONAL"
    else:
        status = "BLOCKED"

    return {
        "score":    score,
        "status":   status,
        "critical": critical,
        "warnings": warnings,
        "info":     info,
        "total":    len(findings),
    }
