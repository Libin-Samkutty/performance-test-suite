#!/usr/bin/env python3
"""
trend_report.py — Build-over-build trend analysis for JMeter results.

Compares current results against historical archived results to detect
performance regressions. Warns if p95 latency increases >20% vs 7-day average.

Usage:
    python trend_report.py --history results/archive/ --current results/
    python trend_report.py --history results/archive/ --current results/ --warn-pct 20
"""

import argparse
import csv
import math
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path


def percentile(sorted_values, pct):
    """Compute the pct-th percentile from a pre-sorted list."""
    if not sorted_values:
        return 0
    k = (len(sorted_values) - 1) * (pct / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_values[int(k)]
    return sorted_values[int(f)] * (c - k) + sorted_values[int(c)] * (k - f)


def parse_jtl(filepath):
    """Parse a JMeter .jtl CSV file and return list of elapsed times and success flags."""
    elapsed_times = []
    total = 0
    errors = 0
    timestamps = []

    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            return None
        for row in reader:
            try:
                elapsed = int(row.get("elapsed", 0))
                success = row.get("success", "true").lower() == "true"
                timestamp = int(row.get("timeStamp", 0))
                elapsed_times.append(elapsed)
                timestamps.append(timestamp)
                total += 1
                if not success:
                    errors += 1
            except (ValueError, KeyError):
                continue

    if total == 0:
        return None

    elapsed_times.sort()

    if total > 1 and timestamps:
        duration_s = max((max(timestamps) - min(timestamps)) / 1000.0, 0.001)
        throughput = total / duration_s
    else:
        throughput = 0

    return {
        "total": total,
        "errors": errors,
        "avg": sum(elapsed_times) / total,
        "p90": percentile(elapsed_times, 90),
        "p95": percentile(elapsed_times, 95),
        "p99": percentile(elapsed_times, 99),
        "max": elapsed_times[-1],
        "error_rate": (errors / total) * 100,
        "throughput": throughput,
    }


def get_file_date(filepath):
    """Extract date from file modification time."""
    mtime = os.path.getmtime(filepath)
    return datetime.fromtimestamp(mtime)


def find_historical_results(history_dir, days=7):
    """Find .jtl files from the last N days in the history directory."""
    cutoff = datetime.now() - timedelta(days=days)
    results = []

    history_path = Path(history_dir)
    if not history_path.is_dir():
        return results

    for jtl_file in sorted(history_path.rglob("*.jtl")):
        file_date = get_file_date(str(jtl_file))
        if file_date >= cutoff:
            metrics = parse_jtl(str(jtl_file))
            if metrics:
                results.append({
                    "file": str(jtl_file),
                    "date": file_date,
                    "metrics": metrics,
                })

    return results


def compute_historical_averages(historical_results):
    """Compute average metrics across historical results."""
    if not historical_results:
        return None

    n = len(historical_results)
    avg_metrics = {
        "avg": sum(r["metrics"]["avg"] for r in historical_results) / n,
        "p90": sum(r["metrics"]["p90"] for r in historical_results) / n,
        "p95": sum(r["metrics"]["p95"] for r in historical_results) / n,
        "p99": sum(r["metrics"]["p99"] for r in historical_results) / n,
        "error_rate": sum(r["metrics"]["error_rate"] for r in historical_results) / n,
        "throughput": sum(r["metrics"]["throughput"] for r in historical_results) / n,
    }
    return avg_metrics


def compute_delta(current, baseline):
    """Compute percentage change from baseline to current."""
    if baseline == 0:
        return 0 if current == 0 else 100.0
    return ((current - baseline) / baseline) * 100.0


def main():
    parser = argparse.ArgumentParser(
        description="Build-over-build trend analysis for JMeter results."
    )
    parser.add_argument(
        "--history",
        required=True,
        help="Path to historical results archive directory",
    )
    parser.add_argument(
        "--current",
        required=True,
        help="Path to current results directory",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days to look back for historical data (default: 7)",
    )
    parser.add_argument(
        "--warn-pct",
        type=float,
        default=20.0,
        help="Warning threshold for percentage increase (default: 20%%)",
    )
    args = parser.parse_args()

    print("\n" + "=" * 70)
    print("Performance Trend Analysis")
    print("=" * 70)
    print(f"  History dir:  {args.history}")
    print(f"  Current dir:  {args.current}")
    print(f"  Lookback:     {args.days} days")
    print(f"  Warn at:      {args.warn_pct}% regression")

    # Load historical data
    historical = find_historical_results(args.history, args.days)
    print(f"\n  Historical results found: {len(historical)}")

    if not historical:
        print("  No historical data available. Skipping trend analysis.")
        print("  TIP: Archive .jtl files to results/archive/ after each run.")
        sys.exit(0)

    baseline = compute_historical_averages(historical)

    # Process current results
    current_path = Path(args.current)
    jtl_files = sorted(current_path.glob("*.jtl"))

    if not jtl_files:
        print(f"  No .jtl files in {args.current}. Nothing to compare.")
        sys.exit(0)

    warnings_found = False

    for jtl_file in jtl_files:
        current_metrics = parse_jtl(str(jtl_file))
        if not current_metrics:
            continue

        print(f"\n{'-'*70}")
        print(f"  File: {jtl_file.name}")
        print(f"{'-'*70}")
        print(f"  {'Metric':<25} {'Current':>12} {'Baseline':>12} {'Delta':>10}")
        print(f"  {'-'*59}")

        trend_checks = [
            ("Avg Response (ms)", "avg", "higher_is_worse"),
            ("p90 Response (ms)", "p90", "higher_is_worse"),
            ("p95 Response (ms)", "p95", "higher_is_worse"),
            ("p99 Response (ms)", "p99", "higher_is_worse"),
            ("Error Rate (%)", "error_rate", "higher_is_worse"),
            ("Throughput (TPS)", "throughput", "lower_is_worse"),
        ]

        for label, key, direction in trend_checks:
            current_val = current_metrics[key]
            baseline_val = baseline[key]
            delta = compute_delta(current_val, baseline_val)

            if direction == "higher_is_worse":
                is_regression = delta > args.warn_pct
            else:
                is_regression = delta < -args.warn_pct

            flag = " ⚠ WARN" if is_regression else ""
            if is_regression:
                warnings_found = True

            print(
                f"  {label:<25} {current_val:>12.2f} {baseline_val:>12.2f} "
                f"{delta:>+9.1f}%{flag}"
            )

    # Summary
    print(f"\n{'='*70}")
    if warnings_found:
        print(
            f"TREND WARNING: Performance regression detected "
            f"(>{args.warn_pct}% vs {args.days}-day average)"
        )
        print("Review the metrics above and investigate root causes.")
    else:
        print(
            f"TREND OK: All metrics within {args.warn_pct}% "
            f"of {args.days}-day baseline."
        )
    print("=" * 70 + "\n")

    # Exit with warning code (not failure) for trend regressions
    sys.exit(2 if warnings_found else 0)


if __name__ == "__main__":
    main()