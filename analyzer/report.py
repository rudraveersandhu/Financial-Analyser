"""Render a multi-page PDF report: summary, charts, and an outlier table.

Uses matplotlib's PdfPages instead of a dedicated PDF library (reportlab)
-- one chart per page, saved into a single PDF. No new dependency needed
since matplotlib is already in the stack, and it keeps chart code and
report code in the same visual language.
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")  # headless: no GUI backend needed for a CLI tool

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages

from analyzer import statistics as stats_mod


def _summary_page(pdf: PdfPages, summary: dict, input_name: str) -> None:
    fig, ax = plt.subplots(figsize=(8.27, 11.69))  # A4 portrait, inches
    ax.axis("off")
    lines = [
        "Personal Finance Report",
        f"Source file: {input_name}",
        "",
        f"Months covered:      {summary['months_covered']}",
        f"Transactions:        {summary['transaction_count']}",
        f"Total income:        Rs {summary['total_income']:,.2f}",
        f"Total spend:         Rs {summary['total_spend']:,.2f}",
        f"Net savings:         Rs {summary['net_savings']:,.2f}",
        f"Savings rate:        {summary['savings_rate_pct']:.1f}%",
        f"Avg monthly spend:   Rs {summary['avg_monthly_spend']:,.2f}",
    ]
    ax.text(
        0.05, 0.95, "\n".join(lines),
        va="top", ha="left", fontsize=13, family="monospace",
        transform=ax.transAxes,
    )
    pdf.savefig(fig)
    plt.close(fig)


def _monthly_spend_chart(pdf: PdfPages, monthly: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(11, 7))
    monthly.plot(kind="bar", stacked=True, ax=ax, colormap="tab20")
    ax.set_title("Monthly Spend by Category")
    ax.set_ylabel("Amount (Rs)")
    ax.set_xlabel("Month")
    ax.legend(loc="upper left", bbox_to_anchor=(1.0, 1.0), fontsize=8)
    fig.tight_layout()
    pdf.savefig(fig)
    plt.close(fig)


def _category_totals_chart(pdf: PdfPages, monthly: pd.DataFrame) -> None:
    totals = monthly.sum().sort_values(ascending=False)
    fig, ax = plt.subplots(figsize=(9, 6))
    totals.plot(kind="barh", ax=ax, color="#4C72B0")
    ax.invert_yaxis()
    ax.set_title("Total Spend by Category (All Time)")
    ax.set_xlabel("Amount (Rs)")
    fig.tight_layout()
    pdf.savefig(fig)
    plt.close(fig)


def _top_merchants_chart(pdf: PdfPages, merchants: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.barh(merchants["merchant"], merchants["total_spent"], color="#DD8452")
    ax.invert_yaxis()
    ax.set_title("Top Merchants by Spend")
    ax.set_xlabel("Amount (Rs)")
    fig.tight_layout()
    pdf.savefig(fig)
    plt.close(fig)


def _outliers_page(pdf: PdfPages, outliers: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(11, 8.5))
    ax.axis("off")
    ax.set_title("Outlier Transactions (>2 std dev from category mean)", fontsize=12, loc="left")

    if outliers.empty:
        ax.text(0.05, 0.9, "No outliers detected.", transform=ax.transAxes)
    else:
        display = outliers.head(20).copy()
        display["date"] = display["date"].dt.strftime("%Y-%m-%d")
        display["spend"] = display["spend"].map(lambda v: f"{v:,.0f}")
        display["z_score"] = display["z_score"].map(lambda v: f"{v:.2f}")
        table = ax.table(
            cellText=display[["date", "category", "merchant", "spend", "z_score"]].values,
            colLabels=["Date", "Category", "Merchant", "Spend (Rs)", "Z-score"],
            loc="center",
            cellLoc="left",
        )
        table.auto_set_font_size(False)
        table.set_fontsize(8)
        table.scale(1, 1.4)

    pdf.savefig(fig)
    plt.close(fig)


def generate_pdf(df: pd.DataFrame, output_path: str, input_name: str = "input.csv") -> None:
    """Build the full multi-page PDF report and write it to output_path."""
    monthly = stats_mod.monthly_category_spend(df)
    merchants = stats_mod.top_merchants(df, n=10)
    outliers = stats_mod.detect_outliers(df)
    summary = stats_mod.summary_stats(df)

    with PdfPages(output_path) as pdf:
        _summary_page(pdf, summary, input_name)
        _monthly_spend_chart(pdf, monthly)
        _category_totals_chart(pdf, monthly)
        _top_merchants_chart(pdf, merchants)
        _outliers_page(pdf, outliers)
