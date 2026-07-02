"""CLI entry point.

Usage:
    python finance.py --input data/bank_transactions_dummy.csv
    python finance.py --input data/bank_transactions_dummy.csv --report
    python finance.py --input data/bank_transactions_dummy.csv --report --output out.pdf
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from analyzer import statistics as stats_mod
from analyzer.categorize import add_categories
from analyzer.report import generate_pdf
from analyzer.utils import load_transactions


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Categorize and analyze bank/UPI transaction CSVs.")
    parser.add_argument("--input", required=True, help="Path to the transaction CSV")
    parser.add_argument("--report", action="store_true", help="Also generate a PDF report")
    parser.add_argument("--output", default=None, help="PDF output path (default: <input>_report.pdf)")
    parser.add_argument("--top-n", type=int, default=10, help="Number of top merchants to show")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    input_path = Path(args.input)

    if not input_path.exists():
        print(f"Error: {input_path} does not exist", file=sys.stderr)
        return 1

    df = load_transactions(str(input_path))
    df = add_categories(df)

    summary = stats_mod.summary_stats(df)
    print("=" * 55)
    print("SUMMARY")
    print("=" * 55)
    print(f"Months covered      : {summary['months_covered']}")
    print(f"Transactions        : {summary['transaction_count']}")
    print(f"Total income        : Rs {summary['total_income']:,.2f}")
    print(f"Total spend         : Rs {summary['total_spend']:,.2f}")
    print(f"Net savings         : Rs {summary['net_savings']:,.2f}")
    print(f"Savings rate        : {summary['savings_rate_pct']:.1f}%")
    print(f"Avg monthly spend   : Rs {summary['avg_monthly_spend']:,.2f}")

    print("\n" + "=" * 55)
    print(f"TOP {args.top_n} MERCHANTS")
    print("=" * 55)
    print(stats_mod.top_merchants(df, n=args.top_n).to_string(index=False))

    outliers = stats_mod.detect_outliers(df)
    print("\n" + "=" * 55)
    print(f"OUTLIERS DETECTED: {len(outliers)}")
    print("=" * 55)
    if not outliers.empty:
        preview = outliers.head(10).copy()
        preview["date"] = preview["date"].dt.strftime("%Y-%m-%d")
        print(preview[["date", "category", "merchant", "spend", "z_score"]].to_string(index=False))

    if args.report:
        output_path = args.output or str(input_path.with_suffix("")) + "_report.pdf"
        generate_pdf(df, output_path, input_name=input_path.name)
        print(f"\nReport written to {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
