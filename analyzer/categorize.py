"""Rule-based categorization of transactions from their narration text.

This is the simplest possible approach to categorization: an ordered list
of (category, keywords) pairs, checked top to bottom, first match wins.
No ML here on purpose — for structured, repetitive narrations like bank
statements, keyword rules get you to ~95% accuracy for a fraction of the
effort a classifier would take. Reach for ML only once rules stop scaling.
"""
from __future__ import annotations

import re

import pandas as pd

# Order matters: earlier rows are checked first, so put specific /
# unambiguous keywords before generic catch-alls (e.g. "Transfer" for any
# leftover "UPI-" narration must be last).
CATEGORY_RULES: list[tuple[str, list[str]]] = [
    ("Income", ["SALARY", "NEFT CR", "PERFORMANCE BONUS", "FESTIVAL BONUS", "INT.PD"]),
    ("Rent", ["RENT"]),
    ("Loan EMI", ["HOMELOAN EMI", "HOME LOAN", " EMI"]),
    ("Investments", ["MF SIP", "CAMS NPCI"]),
    ("Insurance", ["HEALTH INS", "CAR INSURANCE", "LIC OF INDIA", "PREMIUM"]),
    ("Utilities", ["ELECTRICITY", "BSES", "BROADBAND", "POSTPAID", "AIRTEL"]),
    ("Subscriptions", ["NETFLIX", "AMAZON PRIME", "HOTSTAR", "CULT FITNESS"]),
    ("Food Delivery", ["SWIGGY", "ZOMATO"]),
    ("Groceries", ["BIGBASKET", "BLINKIT", "ZEPTO", "DMART", "KIRANA", "PROVISION STORE", "GENERAL STORE"]),
    ("Dining Out", ["STARBUCKS", "CAFE COFFEE DAY", "DOMINOS", "HALDIRAM", "SPICE GARDEN",
                    "COFFEE HOUSE", "BARBEQUE NATION", "RESTAURANT"]),
    ("Transport", ["UBER", "OLA CABS", "RAPIDO", "METRO"]),
    ("Fuel", ["PETROL", "PETROLEUM", "FUEL"]),
    ("Shopping", ["FLIPKART", "MYNTRA", "AJIO", "NYKAA", "CROMA", "RELIANCE DIGITAL", "IKEA",
                  "TANISHQ", "AMAZON"]),
    ("Entertainment", ["BOOKMYSHOW", "PVR", "INOX"]),
    ("Medical", ["PHARMACY", "MEDPLUS", "PRACTO", "HOSPITAL"]),
    ("Education", ["UDEMY", "BOOKSTORE"]),
    ("Travel", ["MAKEMYTRIP", "OYO ROOMS", "GOIBIBO", "FLIGHT BOOKING"]),
    ("ATM Withdrawal", ["NWD-", "ATM CASH WDL"]),
    ("Bank Charges", ["SMS ALERT CHARGES", "DEBIT CARD ANNUAL FEE", "MIN BAL CHARGES",
                      "CHEQUE BOOK ISSUE"]),
    ("Cheque Payment", ["CHQ PAID"]),
    ("Transfer", ["UPI-"]),  # catch-all: anything UPI that didn't match a merchant above
]

# Matches "UPI-<name/merchant>-<vpa>-<bank>-<ref>-<remark>" and pulls out the
# first hyphen-delimited segment, which is always the merchant or person name.
_UPI_MERCHANT = re.compile(r"^UPI-(?P<merchant>[^-]+)-")
# Matches "POS <masked card> <MERCHANT NAME> <CITY>".
_POS_MERCHANT = re.compile(
    r"^POS\s+\S+\s+(?P<merchant>.+?)\s+(?:NEW DELHI|GURGAON|NOIDA|BENGALURU|MUMBAI)$"
)


def categorize(narration: str) -> str:
    """Return the first matching category for a narration, or 'Uncategorized'."""
    text = narration.upper()
    for category, keywords in CATEGORY_RULES:
        if any(keyword in text for keyword in keywords):
            return category
    return "Uncategorized"


def extract_merchant(narration: str) -> str:
    """Best-effort merchant/counterparty name pulled from the narration text.
    This is intentionally simple and won't be perfect (e.g. ACH mandates are
    truncated) -- real narration parsing is an ongoing refinement job, not a
    one-shot function. Good enough here to power a "top merchants" chart.
    """
    text = narration.strip()

    match = _POS_MERCHANT.match(text)
    if match:
        return match.group("merchant").strip().title()

    match = _UPI_MERCHANT.match(text)
    if match:
        return match.group("merchant").strip().title()

    if text.startswith("NWD-"):
        return "ATM Withdrawal"
    if text.startswith("ACH D-"):
        parts = text.split("-")
        return parts[1].strip().title() if len(parts) > 1 else "Direct Debit"
    if text.startswith("CHQ PAID"):
        parts = text.split("-")
        return parts[-1].strip().title() if len(parts) > 1 else "Cheque Payment"

    return "Other"


def add_categories(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of df with 'category' and 'merchant' columns added."""
    df = df.copy()
    df["category"] = df["narration"].apply(categorize)
    df["merchant"] = df["narration"].apply(extract_merchant)
    return df
