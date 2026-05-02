"""
Reads a client Excel file and returns a dict of {sheet_name: DataFrame}.
Handles common ingestion problems: merged headers, extra blank rows,
whitespace in column names, mixed-type columns.
"""

import pandas as pd
from pathlib import Path


def load_excel(file_path) -> dict:
    """
    Accepts a file path (str/Path) or a file-like object (Streamlit UploadedFile).
    Returns {sheet_name: DataFrame} for all non-empty sheets.
    """
    xl = pd.ExcelFile(file_path, engine="openpyxl")
    sheets = {}
    for name in xl.sheet_names:
        df = xl.parse(name)
        df = _clean_dataframe(df, name)
        if not df.empty:
            sheets[name] = df
    return sheets


def _clean_dataframe(df: pd.DataFrame, sheet_name: str) -> pd.DataFrame:
    # Drop rows that are entirely blank
    df = df.dropna(how="all").reset_index(drop=True)

    # Normalize column names: strip whitespace, lowercase
    df.columns = [
        str(c).strip().lower().replace(" ", "_").replace("-", "_")
        for c in df.columns
    ]

    # Drop columns that are entirely unnamed (Unnamed: X artifacts from Excel)
    df = df.loc[:, ~df.columns.str.startswith("unnamed")]

    # Deduplicate column names (Excel files can have repeated headers)
    seen = {}
    new_cols = []
    for c in df.columns:
        if c in seen:
            seen[c] += 1
            new_cols.append(f"{c}_{seen[c]}")
        else:
            seen[c] = 0
            new_cols.append(c)
    df.columns = new_cols

    # Strip string values
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].apply(lambda x: x.strip() if isinstance(x, str) else x)

    return df


def detect_client_type(sheets: dict, configs: dict):
    """
    Auto-detect client type by matching sheet names against config registry.
    Returns the best-matching client key or None.
    """
    sheet_names = set(sheets.keys())
    best_match  = None
    best_score  = 0

    for client_key, config in configs.items():
        expected = set(config["sheets"].keys())
        score    = len(sheet_names & expected)
        if score > best_score:
            best_score  = score
            best_match  = client_key

    return best_match if best_score > 0 else None
