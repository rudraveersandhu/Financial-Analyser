"""Load a raw bank-statement CSV and turn it into a tidy DataFrame.

Real bank exports are messy on purpose (that's the whole point of this
project): amounts split across two columns with blanks instead of zeros,
dates as DD/MM/YYYY strings, thousands separators, stray whitespace. This
module is the one place that mess gets cleaned up, so every other module
can assume a tidy shape.
"""
from __future__ import annotations

import pandas as pd

# Maps the raw HDFC-style export headers to clean, code-friendly names.
RAW_COLUMNS = {
    "Date": "date",
    "Narration": "narration",
    "Chq./Ref.No.": "ref_no",
    "Value Dt": "value_date",
    "Withdrawal Amt.": "withdrawal",
    "Deposit Amt.": "deposit",
    "Closing Balance": "closing_balance",
}

TIDY_COLUMNS = [
    "date",
    "month",
    "narration",
    "ref_no",
    "withdrawal",
    "deposit",
    "amount",
    "direction",
    "closing_balance",
    "value_date",
]


#   def load_transactions(path: str) -> pd.DataFrame:
#   │                  │         │          │
#   │                  │         │          └── Returns a pandas DataFrame
#   │                  │         └──────────── path should be a string
#   │                  └────────────────────── Function parameter
#   └───────────────────────────────────────── Define a function

def load_transactions(path: str) -> pd.DataFrame:
    """Read a raw transaction CSV and return a cleaned, sorted DataFrame.

    Adds two derived columns that the rest of the pipeline relies on:
    - amount: signed value (positive = money in, negative = money out)
    - month: "YYYY-MM" string, used for monthly grouping
    """

    # Dataframe created from the csv
    df = pd.read_csv(path, dtype=str, encoding="utf-8-sig")
    # Dataframe's "columns" renamed to simpler names using the RAW_COLUMNS dictionary reference
    df = df.rename(columns=RAW_COLUMNS)

    # Now we have simpler column naming scheme ready dataframe

    # this is a safety check to see if the CSV contains every column that our program expects to exist.
    missing = set(RAW_COLUMNS.values()) - set(df.columns)
    if missing:
        raise ValueError(f"Input CSV is missing expected columns: {sorted(missing)}")

    # dayfirst=True because Indian bank exports use DD/MM/YYYY, not ISO.
    df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")
    df["value_date"] = pd.to_datetime(df["value_date"], dayfirst=True, errors="coerce")

    for col in ("withdrawal", "deposit", "closing_balance"):

        # the .fillna("") function replaces null values with a blank string so that it is easier to process
        # the .str.replace("," , "", regex=false) replaces the comma with blank empty space or basically removes teh column
        # the .str.strip() replaces white spaces from both the ends
        cleaned = df[col].fillna("").str.replace(",", "", regex=False).str.strip() #using method chaining so essentially we are performing 3 functional calls here

        # this converts the strings number to proper numbers, example, "500" becomes 500.
        # also, the [errors="coerce"] means If you can't convert a value into a number, don't crash and give an exception. Replace it with NaN.
        df[col] = pd.to_numeric(cleaned, errors="coerce").fillna(0.0)

    df["narration"] = df["narration"].fillna("").str.strip()
    df["ref_no"] = df["ref_no"].fillna("").astype(str).str.strip()

    # Count how many rows have missing or invalid dates (NaT)
    bad_dates = int(df["date"].isna().sum())

    if bad_dates:
        print(f"Warning: dropped {bad_dates} row(s) with an unparseable date")
        df = df.dropna(subset=["date"])

    # Only one of withdrawal/deposit is ever populated per row, so this
    # collapses them into a single signed number: negative = spend.
    df["amount"] = df["deposit"] - df["withdrawal"]
    df["direction"] = df["amount"].apply(lambda x: "credit" if x >= 0 else "debit")

    df = df.sort_values("date").reset_index(drop=True)
    df["month"] = df["date"].dt.to_period("M").astype(str)

    return df[TIDY_COLUMNS]

"""
                                    CSV File
                                        │
                                        ▼
                                    Read CSV
                                        │
                                        ▼
                          Rename ugly bank column names
                                        │
                                        ▼
                         Check all required columns exist
                                        │
                                        ▼
                         Convert text dates → real dates
                                        │
                                        ▼
                                Clean numeric columns
                          (remove commas, spaces, blanks)
                                        │
                                        ▼
                             Convert text → numbers
                                        │
                                        ▼
                     Clean narration and reference fields
                                        │
                                        ▼
                           Drop rows with invalid dates
                                        │
                                        ▼
                            Create a signed amount
                               (+credit, −debit)
                                        │
                                        ▼
                         Label each transaction as credit/debit
                                        │
                                        ▼
                                   Sort by date
                                        │
                                        ▼
                            Create a YYYY-MM month column
                                        │
                                        ▼
                        Return a clean, standardized DataFrame

"""
