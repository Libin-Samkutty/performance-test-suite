#!/usr/bin/env python3
"""
check_thresholds.py — Validates JMeter .jtl results against performance thresholds.

Usage:
    python check_thresholds.py --results results/ --config config/thresholds.properties
    python check_thresholds.py --results results/ --config config/thresholds.properties \
        --env-config config/environments.properties --environment staging
"""

import argparse
import csv
import math
import os
import sys
from pathlib import Path


def parse_properties(filepath):
    """Parse a Java-style .properties file into a dict."""
    props = {}
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                props[key.strip()] = value.strip()
    return props


def load_thresholds(config_path, env_config_path=None, environment=None):
    """Load base thresholds and optionally overlay environment-specific ones."""
    thresholds = parse_properties(config_path)

    if env_config_path and environment and os.path.isfile(env_config_path):
        env_props = parse_properties(env_config_path)
        prefix = f"{environment}."
        for key, value in env_props.items():
            if key.startswith(prefix):
                base_key = key[len(prefix):]
                thresholds[base_key] = value
                print(f"  [ENV] Override: {base_key} = {value} (from {environment})")

    return thresholds


def parse_jtl(filepath):
    """Parse a JMeter .jtl CSV result file and return list of sample dicts."""
    samples = []
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            print(f"  WARNING: {filepath} has no headers, skipping.")
            return samples
        for row in reader:
            try:
                sample = {
                    "timestamp": int(row.get("timeStamp", 0)),
                    "elapsed": int(row.get("elapsed", 0)),
                    "label": row.get("label", ""),
                    "response_code": row.get("responseCode", ""),
                    "success": row.get("success", "true").lower() == "true",
                    "latency": int(row.get("Latency", 0)),
                    "connect": int(row.get("Connect", 0)),
                    "bytes": int(row.get("bytes", 0)),
                }
                samples.append(sample)
            except (ValueError, KeyError) as e:
                # Skip malformed rows
                continue
    return samples


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


def compute_metrics(samples):
    """Compute aggregate performance metrics from parsed samples."""
    if not samples:
        return None

    elapsed_times = sorted([s["elapsed"] for s in samples])
    total = len(samples)
    errors = sum(1 for s in samples if not s["success"])

    # HTTP error codes (4xx, 5xx)
    http_errors = 0
    connection_timeouts = 0
    for s in samples:
        code = s["response_code"]
        if code.isdigit():
            code_int = int(code)
            if code_int >= 400:
                http_errors += 1
        else:
            # Non-numeric codes often indicate connection failures
            connection_timeouts += 1

    # Throughput: total samples / test duration in seconds
    if total > 1:
        timestamps = [s["timestamp"] for s in samples]
        duration_ms = max(timestamps) - min(timestamps)
        duration_s = max(duration_ms / 1000.0, 0.001)
        throughput = total / duration_s
    else:
        throughput = 0

    metrics = {
        "total_samples": total,
        "error_count": errors,
        "http_error_count": http_errors,
        "connection_timeout_count": connection_timeouts,
        "avg_response_time": sum(elapsed_times) / total,
        "min_response_time": elapsed_times[0],
        "max_response_time": elapsed_times[-1],
        "p90_response_time": percentile(elapsed_times, 90),
        "p95_response_time": percentile(elapsed_times, 95),
        "p99_response_time": percentile(elapsed_times, 99),
        "http_error_rate": (http_errors / total) * 100,
        "connection_timeout_rate": (connection_timeouts / total) * 100,
        "assertion_failure_rate": (errors / total) * 100,
        "throughput_tps": throughput,
    }
    return metrics


def check_threshold(metric_name, actual_value, max_value, operator="<="):
    """Check a single metric against a threshold. Returns (passed, message)."""
    if operator == "<=":
        passed = actual_value <= max_value
        symbol = "<="
    elif operator == ">=":
        passed = actual_value >= max_value
        symbol = ">="
    else:
        passed = actual_value <= max_value
        symbol = "<="

    status = "PASS" if passed else "FAIL"
    msg = f"  [{status}] {metric_name}: {actual_value:.2f} (threshold: {symbol} {max_value})"
    return passed, msg


def validate_results(metrics, thresholds, result_name):
    """Validate computed metrics against thresholds. Returns (all_passed, messages)."""
    messages = []
    all_passed = True

    messages.append(f"\n{'='*70}")
    messages.append(f"Results: {result_name}")
    messages.append(f"{'='*70}")
    messages.append(f"  Total Samples:      {metrics['total_samples']}")
    messages.append(f"  Errors:             {metrics['error_count']}")
    messages.append(f"  Throughput:         {metrics['throughput_tps']:.2f} TPS")
    messages.append(f"  Avg Response Time:  {metrics['avg_response_time']:.2f} ms")
    messages.append(f"  p90 Response Time:  {metrics['p90_response_time']:.2f} ms")
    messages.append(f"  p95 Response Time:  {metrics['p95_response_time']:.2f} ms")
    messages.append(f"  p99 Response Time:  {metrics['p99_response_time']:.2f} ms")
    messages.append(f"  Max Response Time:  {metrics['max_response_time']:.2f} ms")
    messages.append(f"  HTTP Error Rate:    {metrics['http_error_rate']:.2f}%")
    messages.append(f"  Timeout Rate:       {metrics['connection_timeout_rate']:.2f}%")
    messages.append(f"  Assertion Fail Rate:{metrics['assertion_failure_rate']:.2f}%")
    messages.append(f"{'-'*70}")
    messages.append("  Threshold Checks:")

    checks = [
        ("avg.response.time.max", "avg_response_time", "<="),
        ("p90.response.time.max", "p90_response_time", "<="),
        ("p95.response.time.max", "p95_response_time", "<="),
        ("p99.response.time.max", "p99_response_time", "<="),
        ("max.response.time.max", "max_response_time", "<="),
        ("http.error.rate.max", "http_error_rate", "<="),
        ("connection.timeout.rate.max", "connection_timeout_rate", "<="),
        ("assertion.failure.rate.max", "assertion_failure_rate", "<="),
    ]

    for threshold_key, metric_key, operator in checks:
        if threshold_key in thresholds:
            threshold_value = float(thresholds[threshold_key])
            passed, msg = check_threshold(
                threshold_key, metrics[metric_key], threshold_value, operator
            )
            messages.append(msg)
            if not passed:
                all_passed = False

    # Check throughput thresholds based on result file name
    result_lower = result_name.lower()
    if "restful" in result_lower or "booker" in result_lower:
        tps_key = "min.tps.restful_booker"
    elif "dummyjson" in result_lower or "dummy" in result_lower:
        tps_key = "min.rps.dummyjson"
    else:
        tps_key = None

    if tps_key and tps_key in thresholds:
        min_tps = float(thresholds[tps_key])
        passed, msg = check_threshold(
            tps_key, metrics["throughput_tps"], min_tps, ">="
        )
        messages.append(msg)
        if not passed:
            all_passed = False

    status = "ALL CHECKS PASSED" if all_passed else "THRESHOLD BREACH DETECTED"
    messages.append(f"{'-'*70}")
    messages.append(f"  Result: {status}")
    messages.append(f"{'='*70}")

    return all_passed, messages


def main():
    parser = argparse.ArgumentParser(
        description="Validate JMeter results against performance thresholds."
    )
    parser.add_argument(
        "--results",
        required=True,
        help="Path to results directory containing .jtl files",
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Path to thresholds.properties file",
    )
    parser.add_argument(
        "--env-config",
        default=None,
        help="Path to environments.properties file (optional)",
    )
    parser.add_argument(
        "--environment",
        default=None,
        help="Environment name for threshold overrides (e.g., staging, production)",
    )
    parser.add_argument(
        "--pattern",
        default="*.jtl",
        help="Glob pattern (relative to --results) selecting which .jtl files to validate (default: *.jtl)",
    )
    args = parser.parse_args()

    # Validate inputs
    if not os.path.isfile(args.config):
        print(f"ERROR: Config file not found: {args.config}")
        sys.exit(2)

    results_path = Path(args.results)
    if not results_path.is_dir():
        print(f"ERROR: Results directory not found: {args.results}")
        sys.exit(2)

    # Load thresholds
    print("\n" + "=" * 70)
    print("Performance Threshold Validation")
    print("=" * 70)
    print(f"  Config: {args.config}")
    if args.environment:
        print(f"  Environment: {args.environment}")

    thresholds = load_thresholds(args.config, args.env_config, args.environment)

    # Find and process .jtl files
    jtl_files = sorted(results_path.glob(args.pattern))
    if not jtl_files:
        print(f"\n  WARNING: No files matching '{args.pattern}' found in {args.results}")
        print("  Nothing to validate.")
        sys.exit(0)

    overall_passed = True
    for jtl_file in jtl_files:
        print(f"\n  Processing: {jtl_file.name}")
        samples = parse_jtl(str(jtl_file))

        if not samples:
            print(f"  WARNING: No valid samples in {jtl_file.name}, skipping.")
            continue

        metrics = compute_metrics(samples)
        if metrics is None:
            print(f"  WARNING: Could not compute metrics for {jtl_file.name}")
            continue

        passed, messages = validate_results(metrics, thresholds, jtl_file.name)
        for msg in messages:
            print(msg)

        if not passed:
            overall_passed = False

    # Final summary
    print("\n" + "=" * 70)
    if overall_passed:
        print("OVERALL RESULT: ALL THRESHOLDS MET — Pipeline PASS")
    else:
        print("OVERALL RESULT: THRESHOLD BREACH — Pipeline FAIL")
    print("=" * 70 + "\n")

    sys.exit(0 if overall_passed else 1)


if __name__ == "__main__":
    main()