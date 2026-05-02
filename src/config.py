"""
Client configuration registry.
Each client type defines expected columns, sheet structure, and business rules.
Adding a new client = adding a new block here, no code changes elsewhere.
"""

CLIENT_CONFIGS = {
    "horizon_capital": {
        "display_name": "Horizon Capital Management",
        "sheets": {
            "accounts": {
                "expected_columns": ["account_id", "account_name", "account_type", "inception_date", "base_currency", "custodian", "status"],
                "required":         ["account_id", "account_name", "account_type", "base_currency"],
                "id_column":        "account_id",
                "id_format":        r"^HCM-\d{5}$",
            },
            "securities": {
                "expected_columns": ["isin", "cusip", "security_name", "asset_class", "currency", "exchange", "price"],
                "required":         ["isin", "security_name", "asset_class"],
                "id_column":        "isin",
                "id_format":        r"^[A-Z]{2}[A-Z0-9]{9}\d$",
            },
            "valuations": {
                "expected_columns": ["account_id", "isin", "valuation_date", "quantity", "market_value", "cost_basis"],
                "required":         ["account_id", "isin", "valuation_date", "quantity", "market_value"],
                "id_column":        None,
                "id_format":        None,
            },
        },
        "business_rules": {
            "value_range": {"market_value": (0, 1_000_000_000), "quantity": (0, 10_000_000)},
            "date_columns": ["inception_date", "valuation_date"],
            "currency_column": "base_currency",
            "valid_currencies": ["USD", "EUR", "GBP", "CHF", "JPY"],
            "valid_account_types": ["INDIVIDUAL", "JOINT", "TRUST", "CORPORATE", "IRA"],
            "valid_asset_classes": ["EQUITY", "FIXED_INCOME", "CASH", "ALTERNATIVE", "REAL_ESTATE"],
        },
    },

    "meridian_wealth": {
        "display_name": "Meridian Wealth Advisors",
        "sheets": {
            "clients": {
                "expected_columns": ["client_ref", "full_name", "entity_type", "open_date", "ccy", "advisor", "risk_profile"],
                "required":         ["client_ref", "full_name", "entity_type", "ccy"],
                "id_column":        "client_ref",
                "id_format":        r"^MW\d{6}$",
            },
            "holdings": {
                "expected_columns": ["client_ref", "ticker", "isin", "instrument_name", "quantity", "unit_price", "total_value", "as_of_date"],
                "required":         ["client_ref", "isin", "quantity", "total_value", "as_of_date"],
                "id_column":        None,
                "id_format":        None,
            },
            "transactions": {
                "expected_columns": ["client_ref", "trade_date", "settle_date", "txn_type", "isin", "quantity", "price", "net_amount"],
                "required":         ["client_ref", "trade_date", "txn_type", "isin", "quantity", "net_amount"],
                "id_column":        None,
                "id_format":        None,
            },
        },
        "business_rules": {
            "value_range": {"total_value": (0, 500_000_000), "net_amount": (-100_000_000, 100_000_000)},
            "date_columns": ["open_date", "as_of_date", "trade_date", "settle_date"],
            "currency_column": "ccy",
            "valid_currencies": ["USD", "EUR", "GBP", "AUD", "CAD"],
            "valid_account_types": ["INDIVIDUAL", "JOINT", "TRUST", "LLC", "FOUNDATION"],
            "valid_asset_classes": [],
        },
    },

    "bluerock_advisors": {
        "display_name": "Bluerock Advisory Group",
        "sheets": {
            "portfolio": {
                "expected_columns": ["port_id", "port_name", "type", "start_dt", "currency", "manager", "benchmark", "active"],
                "required":         ["port_id", "port_name", "type", "currency"],
                "id_column":        "port_id",
                "id_format":        r"^BR-[A-Z]{2}-\d{4}$",
            },
            "positions": {
                "expected_columns": ["port_id", "sedol", "isin", "sec_name", "sec_type", "qty", "price", "mkt_val", "pos_date"],
                "required":         ["port_id", "isin", "qty", "mkt_val", "pos_date"],
                "id_column":        None,
                "id_format":        None,
            },
            "cashflows": {
                "expected_columns": ["port_id", "cf_date", "cf_type", "amount", "currency", "description"],
                "required":         ["port_id", "cf_date", "cf_type", "amount"],
                "id_column":        None,
                "id_format":        None,
            },
        },
        "business_rules": {
            "value_range": {"mkt_val": (0, 2_000_000_000), "qty": (-10_000_000, 10_000_000)},
            "date_columns": ["start_dt", "pos_date", "cf_date"],
            "currency_column": "currency",
            "valid_currencies": ["USD", "EUR", "GBP", "SGD", "HKD"],
            "valid_account_types": ["EQUITY", "BALANCED", "FIXED_INCOME", "MULTI_ASSET"],
            "valid_asset_classes": [],
        },
    },
}
