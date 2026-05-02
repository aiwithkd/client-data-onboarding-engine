"""
Generates realistic messy client Excel files for all three client types.
Each file has intentional data quality issues: missing values, wrong formats,
duplicates, out-of-range values, inconsistent naming — mirroring real onboarding chaos.

Run: python src/generate_data.py
Output: sample_data/client_*.xlsx
"""

import pandas as pd
import numpy as np
import random
import re
from datetime import datetime, timedelta
from pathlib import Path
import openpyxl
from openpyxl.styles import PatternFill, Font

random.seed(42)
np.random.seed(42)

OUTPUT_DIR = Path(__file__).parent.parent / "sample_data"
OUTPUT_DIR.mkdir(exist_ok=True)


def random_date(start_year=2018, end_year=2024):
    start = datetime(start_year, 1, 1)
    end = datetime(end_year, 12, 31)
    return start + timedelta(days=random.randint(0, (end - start).days))


def random_isin():
    country = random.choice(["US", "GB", "DE", "FR", "JP", "CH", "AU"])
    body = "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=9))
    check = random.randint(0, 9)
    return f"{country}{body}{check}"


def corrupt_isin(isin):
    """Introduce common ISIN errors."""
    choice = random.randint(0, 3)
    if choice == 0:
        return isin[:2].lower() + isin[2:]          # lowercase country code
    elif choice == 1:
        return isin[:-1]                             # truncated
    elif choice == 2:
        return isin + "X"                            # extra character
    return isin


def maybe_missing(value, rate=0.08):
    return None if random.random() < rate else value


def maybe_corrupt(value, corrupt_fn, rate=0.10):
    return corrupt_fn(value) if random.random() < rate else value


# ── HORIZON CAPITAL ────────────────────────────────────────────────────────────

def generate_horizon_capital():
    n_accounts = 80
    n_securities = 120
    n_valuations = 400

    account_ids = [f"HCM-{str(i).zfill(5)}" for i in range(10001, 10001 + n_accounts)]
    # inject a few bad IDs
    account_ids[5]  = "HCM-ABC"
    account_ids[12] = "hcm-10013"
    account_ids[20] = "HCM-1002O"  # letter O instead of zero
    account_ids[33] = account_ids[10]  # duplicate

    currencies  = ["USD", "EUR", "GBP", "CHF", "JPY"]
    acct_types  = ["INDIVIDUAL", "JOINT", "TRUST", "CORPORATE", "IRA", "INVALID_TYPE"]
    custodians  = ["Schwab", "Fidelity", "Pershing", "TD Ameritrade", ""]

    accounts_data = []
    for i, aid in enumerate(account_ids):
        accounts_data.append({
            "account_id":    aid,
            "account_name":  maybe_missing(f"Account Holder {i+1}", rate=0.05),
            "account_type":  random.choice(acct_types) if i not in [7, 15] else None,
            "inception_date": maybe_missing(random_date().strftime("%Y-%m-%d"), rate=0.07)
                              if i != 25 else "31-13-2020",  # bad date
            "base_currency": maybe_missing(random.choice(currencies), rate=0.06)
                              if i != 18 else "XX",          # invalid currency
            "custodian":     random.choice(custodians),
            "status":        random.choice(["ACTIVE", "ACTIVE", "ACTIVE", "INACTIVE", "PENDING"]),
        })

    accounts_df = pd.DataFrame(accounts_data)

    isins = [random_isin() for _ in range(n_securities)]
    isins[3]  = corrupt_isin(isins[3])
    isins[11] = corrupt_isin(isins[11])
    isins[22] = isins[5]   # duplicate ISIN
    asset_classes = ["EQUITY", "FIXED_INCOME", "CASH", "ALTERNATIVE", "REAL_ESTATE", "UNKNOWN"]

    securities_data = []
    for i, isin in enumerate(isins):
        securities_data.append({
            "isin":          isin,
            "cusip":         maybe_missing("".join(random.choices("0123456789", k=9)), rate=0.15),
            "security_name": maybe_missing(f"Security {i+1} Corp", rate=0.04),
            "asset_class":   maybe_missing(random.choice(asset_classes), rate=0.08),
            "currency":      maybe_missing(random.choice(currencies), rate=0.06),
            "exchange":      random.choice(["NYSE", "NASDAQ", "LSE", "XETRA", ""]),
            "price":         round(random.uniform(1, 5000), 2) if i not in [8, 17] else -99.99,
        })

    securities_df = pd.DataFrame(securities_data)

    valuations_data = []
    for _ in range(n_valuations):
        val_date = random_date(2023, 2024)
        qty = round(random.uniform(10, 50000), 2)
        price = round(random.uniform(1, 2000), 2)
        mkt_val = round(qty * price, 2)
        valuations_data.append({
            "account_id":    maybe_missing(random.choice(account_ids), rate=0.04),
            "isin":          maybe_missing(random.choice(isins), rate=0.03),
            "valuation_date": val_date.strftime("%Y-%m-%d"),
            "quantity":      qty if random.random() > 0.03 else -qty,
            "market_value":  mkt_val if random.random() > 0.02 else mkt_val * 1000,  # inflated
            "cost_basis":    maybe_missing(round(random.uniform(0, mkt_val * 1.2), 2), rate=0.12),
        })

    valuations_df = pd.DataFrame(valuations_data)

    path = OUTPUT_DIR / "client_horizon_capital.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        accounts_df.to_excel(writer, sheet_name="accounts", index=False)
        securities_df.to_excel(writer, sheet_name="securities", index=False)
        valuations_df.to_excel(writer, sheet_name="valuations", index=False)

    print(f"  Generated: {path.name}  ({n_accounts} accounts, {n_securities} securities, {n_valuations} valuations)")
    return path


# ── MERIDIAN WEALTH ────────────────────────────────────────────────────────────

def generate_meridian_wealth():
    n_clients = 60
    n_holdings = 300
    n_transactions = 250

    client_refs = [f"MW{str(i).zfill(6)}" for i in range(100001, 100001 + n_clients)]
    client_refs[4]  = "MW10004X"   # wrong format
    client_refs[9]  = client_refs[3]  # duplicate
    client_refs[17] = None

    entity_types  = ["INDIVIDUAL", "JOINT", "TRUST", "LLC", "FOUNDATION", "UNKNOWN"]
    risk_profiles = ["CONSERVATIVE", "MODERATE", "AGGRESSIVE", "BALANCED", ""]

    clients_data = []
    for i, ref in enumerate(client_refs):
        clients_data.append({
            "client_ref":   ref,
            "full_name":    maybe_missing(f"Client Name {i+1}", rate=0.04),
            "entity_type":  maybe_missing(random.choice(entity_types), rate=0.07),
            "open_date":    maybe_missing(random_date().strftime("%m/%d/%Y"), rate=0.06)
                            if i != 22 else "2024-31-01",
            "ccy":          maybe_missing(random.choice(["USD", "EUR", "GBP", "AUD", "CAD", "ZZZ"]), rate=0.05),
            "advisor":      maybe_missing(f"Advisor {random.randint(1,8)}", rate=0.10),
            "risk_profile": random.choice(risk_profiles),
        })

    clients_df = pd.DataFrame(clients_data)

    isins = [random_isin() for _ in range(80)]
    isins[6] = corrupt_isin(isins[6])
    tickers = [f"{random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}{random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}{random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}" for _ in range(80)]

    holdings_data = []
    for _ in range(n_holdings):
        as_of = random_date(2023, 2024)
        qty   = round(random.uniform(10, 20000), 4)
        price = round(random.uniform(1, 1500), 4)
        total = round(qty * price, 2)
        holdings_data.append({
            "client_ref":     maybe_missing(random.choice(client_refs), rate=0.03),
            "ticker":         maybe_missing(random.choice(tickers), rate=0.15),
            "isin":           maybe_missing(random.choice(isins), rate=0.05),
            "instrument_name": maybe_missing(f"Instrument {random.randint(1,80)}", rate=0.06),
            "quantity":       qty,
            "unit_price":     price,
            "total_value":    total if random.random() > 0.03 else total * -1,
            "as_of_date":     as_of.strftime("%Y-%m-%d"),
        })

    holdings_df = pd.DataFrame(holdings_data)

    txn_types = ["BUY", "SELL", "DIVIDEND", "INTEREST", "FEE", "TRANSFER", "UNKNOWN"]
    txns_data = []
    for _ in range(n_transactions):
        trade_dt  = random_date(2022, 2024)
        settle_dt = trade_dt + timedelta(days=random.choice([0, 1, 2, 3, -1]))  # -1 = settle before trade
        qty   = round(random.uniform(1, 10000), 4)
        price = round(random.uniform(1, 2000), 4)
        txns_data.append({
            "client_ref":  maybe_missing(random.choice(client_refs), rate=0.03),
            "trade_date":  trade_dt.strftime("%Y-%m-%d"),
            "settle_date": settle_dt.strftime("%Y-%m-%d"),
            "txn_type":    maybe_missing(random.choice(txn_types), rate=0.05),
            "isin":        maybe_missing(random.choice(isins), rate=0.04),
            "quantity":    qty,
            "price":       price,
            "net_amount":  round(qty * price * random.choice([1, -1]), 2),
        })

    txns_df = pd.DataFrame(txns_data)

    path = OUTPUT_DIR / "client_meridian_wealth.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        clients_df.to_excel(writer, sheet_name="clients", index=False)
        holdings_df.to_excel(writer, sheet_name="holdings", index=False)
        txns_df.to_excel(writer, sheet_name="transactions", index=False)

    print(f"  Generated: {path.name}  ({n_clients} clients, {n_holdings} holdings, {n_transactions} transactions)")
    return path


# ── BLUEROCK ADVISORS ──────────────────────────────────────────────────────────

def generate_bluerock_advisors():
    n_portfolios = 40
    n_positions  = 350
    n_cashflows  = 180

    port_letters = ["EQ", "FI", "MA", "AL", "RE"]
    port_ids = [f"BR-{random.choice(port_letters)}-{str(i).zfill(4)}" for i in range(1001, 1001 + n_portfolios)]
    port_ids[2]  = "BR1003"        # wrong format
    port_ids[8]  = port_ids[1]     # duplicate
    port_ids[15] = "BR--EQ-1015"   # double dash

    currencies = ["USD", "EUR", "GBP", "SGD", "HKD"]
    port_types = ["EQUITY", "BALANCED", "FIXED_INCOME", "MULTI_ASSET", "HEDGE"]

    portfolio_data = []
    for i, pid in enumerate(port_ids):
        portfolio_data.append({
            "port_id":    pid,
            "port_name":  maybe_missing(f"Portfolio {i+1}", rate=0.04),
            "type":       maybe_missing(random.choice(port_types), rate=0.07),
            "start_dt":   maybe_missing(random_date().strftime("%d-%b-%Y"), rate=0.06),
            "currency":   maybe_missing(random.choice(currencies + ["XX"]), rate=0.05),
            "manager":    maybe_missing(f"Manager {random.randint(1,6)}", rate=0.10),
            "benchmark":  random.choice(["S&P500", "MSCI World", "Bloomberg Agg", ""]),
            "active":     random.choice([True, False, True, True, "Yes", "yes", 1]),
        })

    portfolio_df = pd.DataFrame(portfolio_data)

    isins = [random_isin() for _ in range(100)]
    isins[5]  = corrupt_isin(isins[5])
    isins[14] = corrupt_isin(isins[14])
    isins[30] = isins[20]  # duplicate

    sec_types = ["EQUITY", "BOND", "ETF", "MUTUAL_FUND", "DERIVATIVE", "UNKNOWN"]

    positions_data = []
    for _ in range(n_positions):
        pos_dt = random_date(2023, 2024)
        qty    = round(random.uniform(-500, 50000), 2)
        price  = round(random.uniform(0.01, 3000), 4)
        mkt    = round(abs(qty) * price, 2)
        positions_data.append({
            "port_id":   maybe_missing(random.choice(port_ids), rate=0.03),
            "sedol":     maybe_missing("".join(random.choices("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=7)), rate=0.20),
            "isin":      maybe_missing(random.choice(isins), rate=0.04),
            "sec_name":  maybe_missing(f"Security {random.randint(1,100)}", rate=0.05),
            "sec_type":  maybe_missing(random.choice(sec_types), rate=0.07),
            "qty":       qty,
            "price":     price,
            "mkt_val":   mkt if random.random() > 0.03 else mkt * 9999,
            "pos_date":  pos_dt.strftime("%Y-%m-%d"),
        })

    positions_df = pd.DataFrame(positions_data)

    cf_types = ["CONTRIBUTION", "WITHDRAWAL", "DIVIDEND", "INTEREST", "FEE", "REBALANCE"]
    cf_data  = []
    for _ in range(n_cashflows):
        cf_dt = random_date(2022, 2024)
        cf_data.append({
            "port_id":     maybe_missing(random.choice(port_ids), rate=0.04),
            "cf_date":     cf_dt.strftime("%Y-%m-%d"),
            "cf_type":     maybe_missing(random.choice(cf_types), rate=0.05),
            "amount":      round(random.uniform(-5_000_000, 10_000_000), 2),
            "currency":    maybe_missing(random.choice(currencies), rate=0.06),
            "description": maybe_missing(f"Transaction ref {random.randint(10000,99999)}", rate=0.15),
        })

    cf_df = pd.DataFrame(cf_data)

    path = OUTPUT_DIR / "client_bluerock_advisors.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        portfolio_df.to_excel(writer, sheet_name="portfolio", index=False)
        positions_df.to_excel(writer, sheet_name="positions", index=False)
        cf_df.to_excel(writer, sheet_name="cashflows", index=False)

    print(f"  Generated: {path.name}  ({n_portfolios} portfolios, {n_positions} positions, {n_cashflows} cashflows)")
    return path


if __name__ == "__main__":
    print("Generating sample client data files...\n")
    generate_horizon_capital()
    generate_meridian_wealth()
    generate_bluerock_advisors()
    print("\nDone. Files written to sample_data/")
