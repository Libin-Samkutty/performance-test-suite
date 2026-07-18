#!/usr/bin/env bash
# ============================================================================
# run_tests.sh — Local runner for the JMeter performance test suite
#
# Usage:
#   ./scripts/run_tests.sh                          # Run all tests, production thresholds
#   ./scripts/run_tests.sh --suite restful-booker    # Only restful-booker tests
#   ./scripts/run_tests.sh --suite dummyjson         # Only dummyjson tests
#   ./scripts/run_tests.sh --env staging             # Use staging thresholds
#   ./scripts/run_tests.sh --threads 50              # Override thread count
#   ./scripts/run_tests.sh --jmeter-home /opt/jmeter # Custom JMeter path
#   ./scripts/run_tests.sh --skip-thresholds         # Run tests without threshold check
# ============================================================================

set -euo pipefail

# ─── Defaults ────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

SUITE="all"
ENVIRONMENT="production"
THREADS_OVERRIDE=""
JMETER_HOME="${JMETER_HOME:-}"
SKIP_THRESHOLDS=false
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ─── Argument Parsing ───────────────────────────────────────────────────────
usage() {
  echo "Usage: $0 [OPTIONS]"
  echo ""
  echo "Options:"
  echo "  --suite <all|restful-booker|dummyjson>  Test suite to run (default: all)"
  echo "  --env <production|staging>              Environment thresholds (default: production)"
  echo "  --threads <N>                           Override thread/user count"
  echo "  --jmeter-home <path>                    Path to JMeter installation"
  echo "  --skip-thresholds                       Skip threshold validation"
  echo "  -h, --help                              Show this help"
  exit 0
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --suite)        SUITE="$2"; shift 2 ;;
    --env)          ENVIRONMENT="$2"; shift 2 ;;
    --threads)      THREADS_OVERRIDE="$2"; shift 2 ;;
    --jmeter-home)  JMETER_HOME="$2"; shift 2 ;;
    --skip-thresholds) SKIP_THRESHOLDS=true; shift ;;
    -h|--help)      usage ;;
    *) echo -e "${RED}Unknown option: $1${NC}"; usage ;;
  esac
done

# ─── Locate JMeter ──────────────────────────────────────────────────────────
find_jmeter() {
  if [[ -n "${JMETER_HOME}" && -x "${JMETER_HOME}/bin/jmeter" ]]; then
    echo "${JMETER_HOME}/bin/jmeter"
    return
  fi

  # Try common install locations
  local candidates=(
    "${PROJECT_ROOT}/apache-jmeter-5.6.3/bin/jmeter"
    "/opt/jmeter/bin/jmeter"
    "/usr/local/jmeter/bin/jmeter"
  )

  for c in "${candidates[@]}"; do
    if [[ -x "$c" ]]; then
      echo "$c"
      return
    fi
  done

  # Try PATH
  if command -v jmeter &>/dev/null; then
    command -v jmeter
    return
  fi

  echo ""
}

JMETER_BIN="$(find_jmeter)"

if [[ -z "${JMETER_BIN}" ]]; then
  echo -e "${RED}✗ JMeter not found.${NC}"
  echo "  Set JMETER_HOME or pass --jmeter-home <path>"
  echo "  Download: https://jmeter.apache.org/download_jmeter.cgi"
  exit 1
fi

echo -e "${CYAN}────────────────────────────────────────────────────${NC}"
echo -e "${CYAN}  Performance Test Suite Runner${NC}"
echo -e "${CYAN}────────────────────────────────────────────────────${NC}"
echo -e "  JMeter:      ${JMETER_BIN}"
echo -e "  Suite:       ${SUITE}"
echo -e "  Environment: ${ENVIRONMENT}"
echo -e "  Timestamp:   ${TIMESTAMP}"
[[ -n "${THREADS_OVERRIDE}" ]] && echo -e "  Threads:     ${THREADS_OVERRIDE} (override)"
echo -e "${CYAN}────────────────────────────────────────────────────${NC}"
echo ""

# ─── Prepare directories ────────────────────────────────────────────────────
RESULTS_DIR="${PROJECT_ROOT}/results"
REPORTS_DIR="${PROJECT_ROOT}/reports"

mkdir -p "${RESULTS_DIR}"
mkdir -p "${REPORTS_DIR}/restful-booker"
mkdir -p "${REPORTS_DIR}/dummyjson"

# ─── Helper: run a single JMX ───────────────────────────────────────────────
OVERALL_EXIT=0

run_jmx() {
  local jmx_file="$1"
  local result_name="$2"
  local report_dir="$3"       # empty string = skip HTML report generation

  local jtl_file="${RESULTS_DIR}/${result_name}.jtl"
  local log_file="${RESULTS_DIR}/${result_name}.log"

  # Remove stale outputs so JMeter doesn't complain
  rm -f "${jtl_file}" "${log_file}"
  [[ -n "${report_dir}" ]] && rm -rf "${report_dir:?}"/* 2>/dev/null || true

  echo -e "${YELLOW}▶ Running: ${jmx_file}${NC}"

  local extra_args=()
  extra_args+=("-Jenvironment=${ENVIRONMENT}")
  [[ -n "${THREADS_OVERRIDE}" ]] && extra_args+=("-Jthreads=${THREADS_OVERRIDE}")

  local report_args=()
  if [[ -n "${report_dir}" ]]; then
    mkdir -p "${report_dir}"
    report_args+=("-e" "-o" "${report_dir}")
  fi

  if "${JMETER_BIN}" \
       -n \
       -t "${PROJECT_ROOT}/${jmx_file}" \
       -l "${jtl_file}" \
       -j "${log_file}" \
       "${extra_args[@]}" \
       "${report_args[@]}"; then
    echo -e "${GREEN}  ✓ Completed: ${result_name}${NC}"
  else
    echo -e "${RED}  ✗ JMeter exited with errors: ${result_name}${NC}"
    OVERALL_EXIT=1
  fi

  echo ""
}

# ─── Execute Tests ──────────────────────────────────────────────────────────
if [[ "${SUITE}" == "all" || "${SUITE}" == "restful-booker" ]]; then
  echo -e "${CYAN}═══ Restful-Booker Tests ═══${NC}"

  run_jmx "jmx/restful-booker/auth.jmx" \
           "restful-booker-auth" \
           ""

  run_jmx "jmx/restful-booker/booking.jmx" \
           "restful-booker-booking" \
           "${REPORTS_DIR}/restful-booker"

  run_jmx "jmx/restful-booker/concurrent-update.jmx" \
           "restful-booker-concurrent" \
           ""
fi

if [[ "${SUITE}" == "all" || "${SUITE}" == "dummyjson" ]]; then
  echo -e "${CYAN}═══ DummyJSON Tests ═══${NC}"

  run_jmx "jmx/dummyjson/login.jmx" \
           "dummyjson-login" \
           ""

  run_jmx "jmx/dummyjson/post-load.jmx" \
           "dummyjson-postload" \
           "${REPORTS_DIR}/dummyjson"
fi

# ─── Threshold Validation ───────────────────────────────────────────────────
if [[ "${SKIP_THRESHOLDS}" == false ]]; then
  echo -e "${CYAN}═══ Threshold Validation ═══${NC}"

  if command -v python3 &>/dev/null; then
    PYTHON_BIN="python3"
  elif command -v python &>/dev/null; then
    PYTHON_BIN="python"
  else
    echo -e "${RED}✗ Python not found — skipping threshold check.${NC}"
    PYTHON_BIN=""
  fi

  if [[ -n "${PYTHON_BIN}" ]]; then
    if "${PYTHON_BIN}" "${SCRIPT_DIR}/check_thresholds.py" \
         --results "${RESULTS_DIR}/" \
         --config "${PROJECT_ROOT}/config/thresholds.properties" \
         --environment "${ENVIRONMENT}" \
         --env-config "${PROJECT_ROOT}/config/environments.properties"; then
      echo -e "${GREEN}✓ All thresholds passed.${NC}"
    else
      echo -e "${RED}✗ Threshold validation FAILED.${NC}"
      OVERALL_EXIT=1
    fi
  fi
else
  echo -e "${YELLOW}⚠ Threshold validation skipped (--skip-thresholds).${NC}"
fi

# ─── Trend Analysis ─────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}═══ Trend Analysis ═══${NC}"
TREND_HISTORY="${RESULTS_DIR}/trend_history"
mkdir -p "${TREND_HISTORY}"

if [[ -n "${PYTHON_BIN:-}" ]]; then
  "${PYTHON_BIN}" "${SCRIPT_DIR}/trend_report.py" \
    --current "${RESULTS_DIR}/" \
    --history "${TREND_HISTORY}/" || true
fi

# ─── Summary ────────────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}────────────────────────────────────────────────────${NC}"
if [[ ${OVERALL_EXIT} -eq 0 ]]; then
  echo -e "${GREEN}✓ All tests and validations passed.${NC}"
else
  echo -e "${RED}✗ One or more steps failed — see output above.${NC}"
fi
echo -e "${CYAN}────────────────────────────────────────────────────${NC}"
echo -e "  Reports:  ${REPORTS_DIR}/"
echo -e "  Results:  ${RESULTS_DIR}/"
echo ""

exit ${OVERALL_EXIT}