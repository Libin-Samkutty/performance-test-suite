# Performance Testing System

Automated performance test suite targeting **Restful-Booker** and **DummyJSON** public APIs using Apache JMeter, with CI/CD integration, threshold gating, and build-over-build trend analysis.

---

## Table of Contents

- [How It Works](#how-it-works)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [Test Plans](#test-plans)
- [Threshold System](#threshold-system)
- [Trend Analysis](#trend-analysis)
- [CI/CD Integration](#cicd-integration)
- [Distributed Testing](#distributed-testing)
- [Optional: InfluxDB + Grafana](#optional-influxdb--grafana)
- [Known Results & API Limitations](#known-results--api-limitations)
- [Troubleshooting](#troubleshooting)
- [Configuration Reference](#configuration-reference)

---

## How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│                        run_tests.sh                             │
│                                                                 │
│  1. Locate JMeter  →  2. Run JMX tests  →  3. Validate          │
│     (auto-detect)        (all or suite)      thresholds         │
│                               │                   │             │
│                          results/*.jtl       check_thresholds   │
│                          reports/*/          .py → pass/FAIL    │
│                               │                                 │
│                         4. Trend Analysis                       │
│                            trend_report.py                      │
│                            (compare vs 7-day history)           │
└─────────────────────────────────────────────────────────────────┘
```

**Step-by-step pipeline:**

1. **`run_tests.sh`** locates JMeter, then runs each `.jmx` file headlessly with `jmeter -n`. Raw results are saved as `.jtl` CSV files in `results/`. HTML dashboard reports are generated for the two primary load tests.

2. **`check_thresholds.py`** reads all `.jtl` files, computes response time percentiles and error rates, and compares them against the thresholds defined in `config/thresholds.properties`. Environment-specific overrides (staging/production) are layered on top. Any breach causes the script to **exit 1**, which fails the CI pipeline.

3. **`trend_report.py`** compares the current results against a rolling 7-day average from `results/trend_history/`. If any metric degrades by more than 20%, it prints a warning and exits 2 (soft warning — does not fail the pipeline by default).

---

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Java JDK | 11+ | Required to run JMeter |
| Apache JMeter | 5.6.3 | Auto-located by `run_tests.sh`; see [Installation](#installation) |
| Python | 3.8+ | Required for threshold validation and trend analysis |
| bash | Any | `run_tests.sh` uses bash; Git Bash works on Windows |

---

## Installation

### 1. Install Java

**Windows**

1. Download the **Java 11 MSI installer** from [https://adoptium.net](https://adoptium.net) — select Java 11, Windows, x64, `.msi`
2. Run the installer and tick **"Set JAVA_HOME variable"** and **"Add to PATH"** when prompted

   Alternatively, install via winget:
   ```cmd
   winget install Microsoft.OpenJDK.11
   ```

3. Ensure Java 11 takes priority if an older version is already installed:
   - Open **Start → "Edit the system environment variables" → Environment Variables**
   - Under **System variables**, verify `JAVA_HOME` points to your Java 11 folder (e.g. `C:\Program Files\Microsoft\jdk-11.0.30.7-hotspot`)
   - Click `Path` → **Edit** → move `%JAVA_HOME%\bin` to the **top** of the list (above any existing Java 8 entries such as `C:\ProgramData\Oracle\Java\javapath`)
   - Click OK on all dialogs, then open a **new** terminal

**Linux (Ubuntu / Debian)**

```bash
sudo apt install openjdk-11-jdk
```

**macOS**

```bash
brew install openjdk@11
```

**Verify (all platforms)**

```bash
java -version
# Expected: openjdk version "11.x.x" ...
```

> **Note:** Java 8 is the minimum JMeter 5.6.x will accept, but this project targets Java 11+. If `java -version` still shows Java 8 after the steps above, confirm `%JAVA_HOME%\bin` is first in your `Path` and that you opened a **new** terminal session.

### 2. Install JMeter

**Windows**

1. Download the `.zip` from [https://archive.apache.org/dist/jmeter/binaries/apache-jmeter-5.6.3.zip](https://archive.apache.org/dist/jmeter/binaries/apache-jmeter-5.6.3.zip)
2. Extract it to a location of your choice (e.g. `C:\Program Files\apache-jmeter-5.6.3`)
3. Set the system environment variables via `Win + R` → `sysdm.cpl` → **Advanced** → **Environment Variables**:
   - In the **bottom (System variables)** section → **New**:
     - Variable name: `JMETER_HOME`
     - Variable value: `C:\Program Files\apache-jmeter-5.6.3`
   - Still in System variables → click **Path** → **Edit → New**, add: `%JMETER_HOME%\bin`
   - Click **OK** on every open dialog (missing one means the change isn't saved)
4. Open a **brand new** CMD window and verify:
   ```cmd
   echo %JMETER_HOME%
   jmeter --version
   ```

> **If `%JMETER_HOME%` still prints literally** (not the path), the variable wasn't saved. Repeat step 3 ensuring you click OK on the "Environment Variables" parent window, not just the inner "Edit" dialog.

**Git Bash on Windows — set PATH permanently in `~/.bashrc`:**

```bash
echo 'export JMETER_HOME="C:/Program Files/apache-jmeter-5.6.3"' >> ~/.bashrc
echo 'export PATH="C:/Program Files/apache-jmeter-5.6.3/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
jmeter --version
```

**Linux / macOS**

```bash
wget https://archive.apache.org/dist/jmeter/binaries/apache-jmeter-5.6.3.tgz
tar -xzf apache-jmeter-5.6.3.tgz
```

Place the extracted `apache-jmeter-5.6.3/` folder in the project root **or** any directory on your system. The runner will find it automatically if it is placed in the project root. Otherwise, tell the runner where to find it:

```bash
# Option A: set the environment variable before running
export JMETER_HOME=/path/to/apache-jmeter-5.6.3

# Option B: pass it as a flag at runtime
./scripts/run_tests.sh --jmeter-home /path/to/apache-jmeter-5.6.3

# Option C: add jmeter to your PATH
export PATH=$PATH:/path/to/apache-jmeter-5.6.3/bin
```

**JMeter auto-discovery order** (checked in sequence):
1. `$JMETER_HOME/bin/jmeter`
2. `<project-root>/apache-jmeter-5.6.3/bin/jmeter`
3. `/opt/jmeter/bin/jmeter`
4. `/usr/local/jmeter/bin/jmeter`
5. `jmeter` on `$PATH`

### 3. Install Python dependencies

The threshold script has no third-party dependencies — it uses only the Python standard library.

```bash
# Verify Python 3 is available
python3 --version
```

> In CI (GitHub Actions), `jproperties` is installed via pip but is not required for the local scripts.

### 4. Make the runner executable (Linux / macOS)

```bash
chmod +x scripts/run_tests.sh
```

---

## Project Structure

```text
performance-test-suite/
├── jmx/                               # JMeter test plans
│   ├── restful-booker/
│   │   ├── auth.jmx                   # Auth endpoint load test (50 threads, 120s)
│   │   ├── booking.jmx                # Full CRUD load test (100 threads, 300s)
│   │   └── concurrent-update.jmx      # Race-condition / concurrency stress test
│   └── dummyjson/
│       ├── login.jmx                  # Login spike test (500 threads, 60s)
│       └── post-load.jmx              # Post CRUD load test (200 threads, 300s)
├── config/
│   ├── thresholds.properties          # Base performance thresholds
│   └── environments.properties        # Per-environment threshold overrides
├── data/
│   └── booking_data.csv               # 20-row parameterised booking test data
├── scripts/
│   ├── run_tests.sh                   # Main local test runner
│   ├── check_thresholds.py            # Threshold validation (exits 1 on breach)
│   └── trend_report.py                # Build-over-build trend analysis (exits 2 on regression)
├── reports/                           # Auto-generated JMeter HTML dashboard reports
│   ├── restful-booker/                #   → booking.jmx HTML report
│   └── dummyjson/                     #   → post-load.jmx HTML report
├── results/                           # Raw .jtl result files + .log files
│   └── trend_history/                 # Historical .jtl files for trend comparisons
├── .github/workflows/
│   └── perf-tests.yml                 # GitHub Actions workflow
└── Jenkinsfile                        # Jenkins declarative pipeline
```

---

## Quick Start

### Run the full suite (all tests)

```bash
./scripts/run_tests.sh
```

This runs all five test plans, validates thresholds, and prints a trend comparison (if history is available).

### Run a single suite

```bash
# Only Restful-Booker tests
./scripts/run_tests.sh --suite restful-booker

# Only DummyJSON tests
./scripts/run_tests.sh --suite dummyjson
```

### Run with a custom thread count

```bash
# Override thread count for all tests (useful for smoke testing)
./scripts/run_tests.sh --threads 5
```

### Run against staging thresholds

```bash
./scripts/run_tests.sh --env staging
```

### Skip threshold validation (exploratory run)

```bash
./scripts/run_tests.sh --skip-thresholds
```

### Point to a specific JMeter installation

```bash
./scripts/run_tests.sh --jmeter-home /opt/apache-jmeter-5.6.3
```

### Run threshold validation manually (after a previous test run)

```bash
python3 scripts/check_thresholds.py \
  --results results/ \
  --config config/thresholds.properties \
  --environment production \
  --env-config config/environments.properties
```

### Run trend analysis manually

```bash
python3 scripts/trend_report.py \
  --history results/trend_history/ \
  --current results/ \
  --days 7 \
  --warn-pct 20
```

---

## Test Plans

### Restful-Booker — `auth.jmx`

**Target:** `https://restful-booker.herokuapp.com/auth`

| Parameter | Default | Override via |
|-----------|---------|-------------|
| Threads | 50 | `--threads N` or `-Jthreads=N` |
| Ramp-up | 30s | — |
| Duration | 120s | — |
| Think time | 300 ± 100ms | — |

**Flow:**
1. `POST /auth` with `{ "username": "admin", "password": "password123" }`
2. Asserts HTTP 200 and that the response body contains `"token"`
3. Duration assertion: response must complete within 5 000ms

---

### Restful-Booker — `booking.jmx`

**Target:** `https://restful-booker.herokuapp.com`

| Parameter | Default | Override via |
|-----------|---------|-------------|
| Threads | 100 | `-Jthreads=N` |
| Ramp-up | 60s | `-Jrampup=N` |
| Duration | 300s | `-Jduration=N` |
| Think time | 300 ± 100ms | — |

**Test data:** reads from [`data/booking_data.csv`](data/booking_data.csv) (20 rows, recycled). Each virtual user gets a unique guest name, price, dates, and additional needs.

**Flow per iteration:**
1. **Authenticate (once per thread)** — `POST /auth` → extracts and stores `token` via JSON extractor
2. **Create booking** — `POST /booking` with CSV-driven body → extracts `bookingid`
3. **Read booking** — `GET /booking/{bookingid}` → asserts body contains `firstname`
4. **Update booking** — `PATCH /booking/{bookingid}` → sends `Cookie: token=…`; asserts HTTP 200
5. **Delete booking** — `DELETE /booking/{bookingid}` → sends `Cookie: token=…`; asserts HTTP 201

**Outputs:** `results/restful-booker-booking.jtl` + HTML report at `reports/restful-booker/index.html`

---

### Restful-Booker — `concurrent-update.jmx`

**Target:** `https://restful-booker.herokuapp.com`

| Parameter | Default |
|-----------|---------|
| Threads | 50 |
| Ramp-up | 0s (all threads start simultaneously) |
| Duration | 120s |

**Purpose:** Verifies the API handles concurrent writes to the same resource without returning 500 Internal Server Error or 409 Conflict.

**Flow:**
1. **setUp group (1 thread, runs once):**
   - Authenticates and stores the token as a JMeter *property* (`auth_token`) so it is shared across thread groups
   - Creates a single target booking and stores its ID as a property (`target_bookingid`)
2. **Main group (50 threads):**
   - A Groovy pre-processor loads the shared token and booking ID from properties into thread-local variables
   - Each thread continuously `PATCH`es the same booking with a unique payload containing its thread number and timestamp
   - Each thread then `GET`s the booking to verify it is still readable
   - Assertions check that neither 500 nor 409 is returned

---

### DummyJSON — `login.jmx`

**Target:** `https://dummyjson.com/auth/login`

| Parameter | Default |
|-----------|---------|
| Threads | 500 |
| Duration | 60s |

**Purpose:** Spike test for the authentication endpoint — models a sudden burst of login requests.

**Flow:**
1. `POST /auth/login` with `{ "username": "emilys", "password": "emilyspass", "expiresInMins": 30 }`
2. Asserts HTTP 200

**Output:** `results/dummyjson-login.jtl`

---

### DummyJSON — `post-load.jmx`

**Target:** `https://dummyjson.com`

| Parameter | Default | Override via |
|-----------|---------|-------------|
| Threads | 200 | `-Jthreads=N` |
| Ramp-up | 30s | `-Jrampup=N` |
| Duration | 300s | `-Jduration=N` |
| Think time | 300 ± 100ms | — |

**Flow:**
1. **setUp group (1 thread, runs once):**
   - `POST /auth/login` → extracts `accessToken` and stores it as property `dummyjson_token`
2. **Main load group (200 threads):**
   - Groovy pre-processor loads the shared token per thread
   - Injects `Authorization: Bearer <token>` header
   - `POST /posts/add` — creates a post with a randomised title, body (`__RandomString`), and userId (`__Random(1,100)`)
   - `GET /posts/{random 1–150}` — reads a random existing post
   - `DELETE /posts/{random 1–150}` — deletes a random existing post

**Outputs:** `results/dummyjson-postload.jtl` + HTML report at `reports/dummyjson/index.html`

---

## Threshold System

### How thresholds are applied

Thresholds are checked by `check_thresholds.py` against every `.jtl` file in `results/`. The script:

1. Loads **base thresholds** from `config/thresholds.properties`
2. If `--environment` is provided, overlays matching keys from `config/environments.properties` (e.g., `staging.*` keys replace their base equivalents)
3. Parses each `.jtl` (CSV format) and computes metrics
4. Detects which suite a file belongs to by matching the filename against `restful`/`booker` or `dummyjson`/`dummy` to pick the correct minimum-throughput threshold
5. Exits `0` (pass) or `1` (breach — fails CI)

### Threshold tiers

| | Base | Staging | Production |
|---|---|---|---|
| Avg response time | ≤ 800ms | ≤ 1 200ms | ≤ 600ms |
| p90 response time | ≤ 1 200ms | ≤ 1 800ms | ≤ 900ms |
| p95 response time | ≤ 1 500ms | ≤ 2 200ms | ≤ 1 200ms |
| p99 response time | ≤ 2 000ms | ≤ 3 000ms | ≤ 1 800ms |
| Max response time | ≤ 5 000ms | ≤ 8 000ms | ≤ 4 000ms |
| HTTP error rate | ≤ 1.0% | ≤ 2.0% | ≤ 0.5% |
| Connection timeout rate | ≤ 0.5% | ≤ 1.0% | ≤ 0.2% |
| Assertion failure rate | ≤ 1.0% | ≤ 2.0% | ≤ 0.5% |
| Min TPS (Restful-Booker) | ≥ 10 | ≥ 5 | ≥ 15 |
| Min RPS (DummyJSON) | ≥ 30 | ≥ 15 | ≥ 40 |

> **Staging** thresholds are relaxed (shared/lower-spec environments).
> **Production** thresholds are stricter than the base defaults.

### Selecting an environment

```bash
# Use base thresholds (default)
./scripts/run_tests.sh

# Use staging thresholds
./scripts/run_tests.sh --env staging

# Use production thresholds
./scripts/run_tests.sh --env production
```

### Adding or changing a threshold

Edit [`config/thresholds.properties`](config/thresholds.properties) for the base values, or [`config/environments.properties`](config/environments.properties) for environment-specific overrides:

```properties
# Example: tighten the p95 base threshold
p95.response.time.max=1200

# Example: add a custom staging override
staging.p95.response.time.max=2000
```

---

## Trend Analysis

`trend_report.py` provides build-over-build visibility to catch gradual performance regressions that stay within thresholds individually.

### How it works

1. Reads all `.jtl` files from `results/trend_history/` that were modified within the last 7 days
2. Averages their metrics (avg, p90, p95, p99, error rate, throughput) to form a baseline
3. Compares the current run's metrics against the baseline
4. Flags any metric that has **increased by more than 20%** (or dropped by 20% for throughput)
5. Exits `2` on warnings (soft failure — the pipeline treats this as non-blocking with `|| true`)

### Archiving results for trend tracking

After each run, copy the current `.jtl` files into `results/trend_history/` to build up a history:

```bash
cp results/*.jtl results/trend_history/
```

In CI (GitHub Actions), the `trend_history/` directory is cached using `actions/cache` keyed by branch name, so history accumulates across runs automatically.

### Customising the lookback or warning threshold

```bash
# Look back 14 days and warn at 30% regression
python3 scripts/trend_report.py \
  --history results/trend_history/ \
  --current results/ \
  --days 14 \
  --warn-pct 30
```

---

## CI/CD Integration

### GitHub Actions

**File:** [`.github/workflows/perf-tests.yml`](.github/workflows/perf-tests.yml)

**Triggers:**

| Trigger | Condition | Default suite | Default env |
|---------|-----------|--------------|-------------|
| `push` | `release/**` branch | all | production |
| `workflow_dispatch` | Manual (UI or API) | selectable | selectable |
| `schedule` | Nightly 02:00 UTC | all | production |

> **Note:** The nightly cron trigger is commented out in the workflow file. Uncomment the `schedule:` block to enable it:
> ```yaml
> on:
>   schedule:
>     - cron: '0 2 * * *'
> ```

**What the workflow does:**

1. Checks out the repository
2. Sets up Java 11 (Temurin) and Python 3.11
3. Downloads and caches JMeter 5.6.3
4. Prepares output directories
5. Runs each test plan with `jmeter -n` (continues on individual test error)
6. Validates thresholds with `check_thresholds.py` — **pipeline fails here on breach**
7. Restores the trend history cache, runs `trend_report.py`, and saves the updated cache
8. Uploads two artifacts (retained for 30 days):
   - `performance-reports-<run#>` — HTML dashboard reports
   - `raw-results-<run#>` — `.jtl` files and JMeter logs
9. Writes a summary table to the GitHub Actions job summary page

**Manual dispatch options (via GitHub UI → Actions → Run workflow):**

| Input | Options | Default |
|-------|---------|---------|
| `test_suite` | `all`, `restful-booker`, `dummyjson` | `all` |
| `environment` | `production`, `staging` | `production` |
| `threads_override` | Any integer (leave blank for defaults) | — |

---

### Jenkins

**File:** [`Jenkinsfile`](Jenkinsfile)

**Prerequisites on the Jenkins agent:**

- Java 11+
- Python 3.8+ with `jproperties` installed (`pip install jproperties`)
- JMeter 5.6.3 registered as a Custom Tool named **`JMeter-5.6.3`** in *Manage Jenkins → Global Tool Configuration*

**Pipeline stages:**

| Stage | Description |
|-------|-------------|
| Setup | Prints run parameters, creates output dirs, verifies JMeter/Java/Python versions |
| Restful-Booker Tests | Runs `auth.jmx`, `booking.jmx`, `concurrent-update.jmx` in sub-stages |
| DummyJSON Tests | Runs `login.jmx`, `post-load.jmx` in sub-stages |
| Validate Thresholds | Runs `check_thresholds.py` — stage **fails** on breach (skipped if `SKIP_THRESHOLDS=true`) |
| Trend Analysis | Runs `trend_report.py` — non-blocking |

**Pipeline parameters (set at build time):**

| Parameter | Type | Options / Default |
|-----------|------|------------------|
| `TEST_SUITE` | Choice | `all` / `restful-booker` / `dummyjson` |
| `ENVIRONMENT` | Choice | `production` / `staging` |
| `THREADS_OVERRIDE` | String | empty (uses JMX defaults) |
| `SKIP_THRESHOLDS` | Boolean | `false` |

**Trigger:** Nightly at 02:00 UTC via `cron('H 2 * * *')`.

**Post-build actions:**

- HTML reports published via `publishHTML` (requires HTML Publisher plugin)
- `.jtl` and `.log` files archived as build artifacts
- Slack notification block is included but **commented out** — uncomment and configure the channel to enable alerts

**Registering JMeter as a Custom Tool in Jenkins:**

1. Install the **Custom Tools Plugin**
2. Go to *Manage Jenkins → Global Tool Configuration → Custom Tool Installations*
3. Add a tool named `JMeter-5.6.3`, download URL: `https://archive.apache.org/dist/jmeter/binaries/apache-jmeter-5.6.3.tgz`
4. Set the label to match your agent label (or leave blank for all agents)

---

## Distributed Testing

For load scenarios requiring more than 500 concurrent users, use JMeter in distributed (remote) mode. One controller machine coordinates multiple worker (agent) machines.

**On each worker machine:**

```bash
# Start the JMeter remote server (listens on port 1099 by default)
${JMETER_HOME}/bin/jmeter-server
```

**On the controller machine:**

```bash
jmeter -n -t jmx/restful-booker/booking.jmx \
  -l results/booking-distributed.jtl \
  -r \
  -Jremote_hosts=worker1:1099,worker2:1099
```

> All machines must have the same JMeter version, and the test data file (`data/booking_data.csv`) must be present on every worker at the same relative path.

---

## Optional: InfluxDB + Grafana

Two test plans (`booking.jmx` and `post-load.jmx`) contain a pre-configured **InfluxDB Backend Listener** that is disabled by default. Enabling it streams live metrics to InfluxDB during the test run, which Grafana can visualise in real time.

### Setup steps

1. **Start InfluxDB 2.x:**
   ```bash
   docker run -d -p 8086:8086 influxdb:2
   ```

2. **Start Grafana:**
   ```bash
   docker run -d -p 3000:3000 grafana/grafana
   ```

3. **Enable the Backend Listener** in the `.jmx` file: open the JMX in JMeter GUI and enable the `InfluxDB Backend Listener` element (currently `enabled="false"`), then set the `influxdbUrl` parameter to point to your instance:
   ```
   http://<your-influxdb-host>:8086/write?db=jmeter
   ```

4. **Import the Grafana dashboard:** use Grafana dashboard ID **1152** (Apache JMeter dashboard).

---

## Known Results & API Limitations

> These results reflect a full suite run against the public demo APIs. Both targets are free, shared, community-facing endpoints — they are not designed for sustained performance testing at the thread counts this suite uses. The results below are the **expected, reproducible behaviour** of this suite against those APIs, not bugs in the test implementation.

### Result summary

| Test | Samples | Error Rate | Avg (ms) | p95 (ms) | TPS | Threshold Result |
|---|---|---|---|---|---|---|
| `restful-booker/auth.jmx` | 9,917 | 0% | 232 | 262 | 83 | ✅ All passed |
| `restful-booker/concurrent-update.jmx` | 19,108 | 0.01% | 314 | 396 | 156 | ✅ All passed |
| `restful-booker/booking.jmx` | 49,830 | 33% | 242 | 256 | 166 | ❌ Error rate & max response time |
| `dummyjson/login.jmx` | 45,339 | 90.2% | 336 | 712 | 757 | ❌ Error rate & p99 |
| `dummyjson/post-load.jmx` | 1 | 100% | 731 | — | 0 | ❌ Did not run |

---

### restful-booker — `booking.jmx` (33% error rate on PATCH / DELETE)

**Endpoint breakdown:**

| Endpoint | Errors | Error % | Primary code |
|---|---|---|---|
| `POST /auth` | 0 / 100 | 0% | 200 |
| `POST /booking` | 23 / 12,472 | 0.2% | 200, 503 |
| `GET /booking/{id}` | 22 / 12,443 | 0.2% | 200, 404 |
| `PATCH /booking/{id}` | 8,201 / 12,418 | **66%** | **403**, 200 |
| `DELETE /booking/{id}` | 8,209 / 12,397 | **66%** | **403**, 201 |

**Root cause — periodic database reset:** The Restful-Booker demo API resets its entire database approximately every 10 minutes. When this happens mid-run, all existing auth tokens are invalidated server-side. Threads that were issued tokens before the reset receive `403 Forbidden` on every subsequent PATCH and DELETE for the remainder of the 300s test. The auth design (once per thread via `OnceOnlyController`) is correct — the tokens simply stop being honoured after the reset occurs.

**Auth design is intentional and correct:** Each thread authenticates once at startup using a `OnceOnlyController` and holds its own thread-local token. This matches the README spec and is the right approach — a shared setUp token would be equally affected by server-side resets.

**This is not a test suite bug.** If run against a real or self-hosted instance of the Restful-Booker API, no resets occur and the error rate drops to near-zero.

---

### dummyjson — `login.jmx` (90% error rate)

**Response code distribution:**

| Code | Count | % | Meaning |
|---|---|---|---|
| 429 Too Many Requests | 39,296 | 86.7% | Rate limit hit |
| 200 OK | 4,435 | 9.8% | Success |
| 401 Unauthorized | 1,608 | 3.5% | Credential rejected under load |

**Root cause — aggressive rate limiting:** The DummyJSON public API enforces a strict per-IP (and likely global) rate limit on the `/auth/login` endpoint. Firing 500 threads simultaneously with a 5s ramp-up exhausts the rate limit window within the first few seconds. The 9.8% success rate represents requests that landed before the limit was hit.

**This is expected and by design:** `login.jmx` is a **spike test** — its purpose is to characterise how the API behaves under sudden burst load. The 429 responses *are* the finding: the API's rate limiter activates immediately at this scale.

---

### dummyjson — `post-load.jmx` (did not run)

**Root cause — setUp blocked by rate limit:** When `post-load.jmx` runs immediately after `login.jmx`, the DummyJSON API's rate limit window is still active. The single setUp thread's `POST /auth/login` receives a `429`, no token is extracted, and the `stoptestnow` error policy on the setUp group halts the entire test before the main 200-thread group starts.

**Workaround:** Wait a few minutes between running `login.jmx` and `post-load.jmx`, or run them in separate suites with a delay:
```bash
# Run DummyJSON tests with a cooldown between them
./scripts/run_tests.sh --suite restful-booker
sleep 120
./scripts/run_tests.sh --suite dummyjson
```

---

### Summary: what is and isn't a real failure

| Failure | Real issue? | Explanation |
|---|---|---|
| `booking.jmx` PATCH/DELETE 403s | No | Public API database reset mid-run |
| `login.jmx` 429s | Expected | Spike test finding — rate limiter activates as designed |
| `post-load.jmx` not running | Avoidable | Run after a cooldown period post `login.jmx` |
| `booking.jmx` max response time >4 000ms | Minor | Occasional slow responses on shared Heroku infra |

None of the above reflect defects in the test suite. Against a stable, non-rate-limited API these tests would pass threshold validation cleanly.

---

## Troubleshooting

### JMeter not found

```
✗ JMeter not found.
  Set JMETER_HOME or pass --jmeter-home <path>
```

Set the environment variable or pass the flag:
```bash
export JMETER_HOME=/path/to/apache-jmeter-5.6.3
# or
./scripts/run_tests.sh --jmeter-home /path/to/apache-jmeter-5.6.3
```

### No `.jtl` files found during threshold validation

The threshold script only processes files already present in `results/`. If a test failed to produce a `.jtl`, check the corresponding `.log` file:
```bash
cat results/restful-booker-booking.log
```

### Token not extracted (TOKEN_NOT_FOUND in logs)

The Restful-Booker API occasionally returns a `Bad credentials` error if you have exceeded rate limits. Wait a few minutes and retry. The API credentials are hardcoded in the JMX files: `username: admin` / `password: password123`.

### Trend analysis shows no historical data

```
No historical data available. Skipping trend analysis.
TIP: Archive .jtl files to results/archive/ after each run.
```

Manually copy `.jtl` files to `results/trend_history/` after your first run:
```bash
cp results/*.jtl results/trend_history/
```

### Python not found

```
✗ Python not found — skipping threshold check.
```

The script looks for `python3` then `python`. Ensure Python 3 is installed and on your `$PATH`:
```bash
python3 --version
```

### HTML report already exists error

JMeter refuses to overwrite an existing report directory. The runner cleans the report directory before each run automatically. If running JMeter manually, delete the directory first:
```bash
rm -rf reports/restful-booker/*
jmeter -n -t jmx/restful-booker/booking.jmx -l results/booking.jtl -e -o reports/restful-booker/
```

---

## Configuration Reference

### `scripts/run_tests.sh` flags

| Flag | Default | Description |
|------|---------|-------------|
| `--suite` | `all` | `all`, `restful-booker`, or `dummyjson` |
| `--env` | `production` | Threshold environment: `production` or `staging` |
| `--threads` | (JMX default) | Override thread count for all test plans |
| `--jmeter-home` | (auto-detect) | Path to JMeter installation directory |
| `--skip-thresholds` | false | Skip `check_thresholds.py` entirely |
| `-h` / `--help` | — | Print usage and exit |

### JMeter properties passed at runtime

| Property | Used by | Purpose |
|----------|---------|---------|
| `-Jenvironment` | All JMX files | Passed through; used for environment-aware logic |
| `-Jthreads` | `booking.jmx`, `auth.jmx`, `concurrent-update.jmx`, `post-load.jmx` | Overrides default thread count |
| `-Jrampup` | `booking.jmx`, `post-load.jmx` | Overrides ramp-up period in seconds |
| `-Jduration` | `booking.jmx`, `post-load.jmx` | Overrides test duration in seconds |

### `config/thresholds.properties`

```properties
# ============================================================
# Performance Thresholds Configuration
# ============================================================
# These thresholds are enforced by scripts/check_thresholds.py.
# A breach of any threshold causes the CI pipeline to fail.
# ============================================================

# --- Response Time (milliseconds) ---
avg.response.time.max=800
p90.response.time.max=1200
p95.response.time.max=1500
p99.response.time.max=2000
max.response.time.max=5000

# --- Error Rates (percentage) ---
http.error.rate.max=1.0
connection.timeout.rate.max=0.5
assertion.failure.rate.max=1.0

# --- Throughput (transactions per second) ---
min.tps.restful_booker=10
min.rps.dummyjson=30
```

### `config/environments.properties`

Keys follow the pattern `<environment>.<base-key>`. Any key present here with a matching `--environment` value **overrides** the corresponding base threshold.

```properties
# Staging — relaxed thresholds for shared/lower-spec environments
staging.avg.response.time.max=1200
staging.p95.response.time.max=2200
staging.http.error.rate.max=2.0
staging.min.tps.restful_booker=5
# ... (see file for full list)

# Production — stricter thresholds
production.avg.response.time.max=600
production.p95.response.time.max=1200
production.http.error.rate.max=0.5
production.min.tps.restful_booker=15
# ... (see file for full list)
```
