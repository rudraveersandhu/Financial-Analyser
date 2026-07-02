"""Aggregations: monthly category spend, top merchants, and outliers.

Everything here works off the tidy DataFrame produced by
`analyzer.utils.load_transactions` + `analyzer.categorize.add_categories`,
i.e. it expects columns: date, month, amount, category, merchant.
"""
from __future__ import annotations

import pandas as pd

INCOME_LIKE = {"Income"}


def _spend_only(df: pd.DataFrame) -> pd.DataFrame:
    """Debit rows only, with a positive 'spend' column, income excluded."""
    spend = df[(df["amount"] < 0) & (~df["category"].isin(INCOME_LIKE))].copy()
    spend["spend"] = -spend["amount"]
    return spend


def monthly_category_spend(df: pd.DataFrame) -> pd.DataFrame:
    """Pivot table: rows = month, columns = category, values = total spend."""
    spend = _spend_only(df)
    pivot = spend.pivot_table(
        index="month", columns="category", values="spend", aggfunc="sum", fill_value=0.0
    )
    return pivot.sort_index()


def top_merchants(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """Top-N merchants by total spend, with transaction counts."""
    spend = _spend_only(df)
    grouped = (
        spend.groupby("merchant")
        .agg(total_spent=("spend", "sum"), transactions=("spend", "count"))
        .sort_values("total_spent", ascending=False)
        .head(n)
        .reset_index()
    )
    return grouped


def detect_outliers(df: pd.DataFrame, z_thresh: float = 2.0) -> pd.DataFrame:
    """Debit transactions more than `z_thresh` std deviations from their
    category's mean spend -- i.e. unusually large purchases for that category.
    """
    spend = _spend_only(df)

    cat_stats = spend.groupby("category")["spend"].agg(cat_mean="mean", cat_std="std")
    spend = spend.join(cat_stats, on="category")
    # A category with only one transaction has std=NaN -- can't z-score it,
    # so it simply can't produce an outlier (nothing to compare against yet).
    spend["z_score"] = (spend["spend"] - spend["cat_mean"]) / spend["cat_std"]

    outliers = spend[spend["z_score"].abs() > z_thresh].copy()
    outliers = outliers.sort_values("z_score", ascending=False)
    return outliers[["date", "narration", "category", "merchant", "spend", "cat_mean", "cat_std", "z_score"]]


def summary_stats(df: pd.DataFrame) -> dict:
    """Headline numbers for the whole statement period."""
    income = float(df.loc[df["amount"] > 0, "amount"].sum())
    spend = float(-df.loc[df["amount"] < 0, "amount"].sum())
    months = df["month"].nunique()

    return {
        "months_covered": int(months),
        "transaction_count": int(len(df)),
        "total_income": income,
        "total_spend": spend,
        "net_savings": income - spend,
        "savings_rate_pct": (income - spend) / income * 100 if income else 0.0,
        "avg_monthly_spend": spend / months if months else 0.0,
    }
