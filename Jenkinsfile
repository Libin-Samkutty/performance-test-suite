// ============================================================================
// Jenkinsfile — Performance Test Suite (Jenkins Declarative Pipeline)
//
// Prerequisites on the Jenkins agent:
//   • Java 11+
//   • Python 3.8+ with 'jproperties' package
//   • JMeter 5.6.x installed (set JMETER_HOME or tool name below)
// ============================================================================

pipeline {
    agent any

    options {
        timeout(time: 90, unit: 'MINUTES')
        timestamps()
        buildDiscarder(logRotator(numToKeepStr: '30', artifactNumToKeepStr: '15'))
        disableConcurrentBuilds()
    }

    parameters {
        choice(
            name: 'TEST_SUITE',
            choices: ['all', 'restful-booker', 'dummyjson'],
            description: 'Which test suite to execute'
        )
        choice(
            name: 'ENVIRONMENT',
            choices: ['production', 'staging'],
            description: 'Environment-specific threshold profile'
        )
        string(
            name: 'THREADS_OVERRIDE',
            defaultValue: '',
            description: 'Override default thread/user count (leave empty for defaults)'
        )
        booleanParam(
            name: 'SKIP_THRESHOLDS',
            defaultValue: false,
            description: 'Skip threshold validation (useful for exploratory runs)'
        )
        booleanParam(
            name: 'ENABLE_OBSERVABILITY',
            defaultValue: false,
            description: 'Start InfluxDB + Grafana via docker compose and stream metrics for live dashboards'
        )
    }

    environment {
        JMETER_HOME    = tool name: 'JMeter-5.6.3', type: 'com.cloudbees.jenkins.plugins.customtools.CustomTool'
        JMETER_BIN     = "${JMETER_HOME}/bin/jmeter"
        RESULTS_DIR    = "${WORKSPACE}/results"
        REPORTS_DIR    = "${WORKSPACE}/reports"
        TIMESTAMP      = sh(script: 'date +%Y%m%d_%H%M%S', returnStdout: true).trim()
    }

    // triggers {
    //     // Nightly at 02:00 UTC (mirrors GitHub Actions schedule)
    //     cron('H 2 * * *')
    // }

    stages {
        // ────────────────────────────────────────────
        // Setup
        // ────────────────────────────────────────────
        stage('Setup') {
            steps {
                echo "╔══════════════════════════════════════════════╗"
                echo "║  Performance Test Suite — Jenkins Pipeline   ║"
                echo "╚══════════════════════════════════════════════╝"
                echo "Suite:       ${params.TEST_SUITE}"
                echo "Environment: ${params.ENVIRONMENT}"
                echo "Timestamp:   ${TIMESTAMP}"

                sh '''
                    mkdir -p "${RESULTS_DIR}"
                    mkdir -p "${REPORTS_DIR}/restful-booker"
                    mkdir -p "${REPORTS_DIR}/dummyjson"
                '''

                sh '"${JMETER_BIN}" --version'
                sh 'java -version'
                sh 'python3 --version || python --version'
            }
        }

        // ────────────────────────────────────────────
        // Observability Stack (opt-in)
        // ────────────────────────────────────────────
        stage('Start Observability Stack') {
            when {
                expression { params.ENABLE_OBSERVABILITY }
            }
            steps {
                sh 'docker compose -f docker/docker-compose.yml up -d influxdb grafana'
                sh 'bash scripts/setup_influxdb.sh'
            }
        }

        // ────────────────────────────────────────────
        // Restful-Booker Tests
        // ────────────────────────────────────────────
        stage('Restful-Booker Tests') {
            when {
                expression {
                    params.TEST_SUITE == 'all' || params.TEST_SUITE == 'restful-booker'
                }
            }
            stages {
                stage('RB: Auth') {
                    steps {
                        sh """
                            rm -f "${RESULTS_DIR}/restful-booker-auth.jtl"
                            "${JMETER_BIN}" -n \
                                -t jmx/restful-booker/auth.jmx \
                                -l "${RESULTS_DIR}/restful-booker-auth.jtl" \
                                -j "${RESULTS_DIR}/restful-booker-auth.log" \
                                -Jenvironment=${params.ENVIRONMENT} \
                                ${params.THREADS_OVERRIDE ? "-Jthreads=${params.THREADS_OVERRIDE}" : ''} \
                                ${params.ENABLE_OBSERVABILITY ? '-Jinfluxdb_url=http://localhost:8086/write?db=jmeter' : ''}
                        """
                    }
                }

                stage('RB: Booking CRUD') {
                    steps {
                        sh """
                            rm -f "${RESULTS_DIR}/restful-booker-booking.jtl"
                            rm -rf "${REPORTS_DIR}/restful-booker/"*
                            "${JMETER_BIN}" -n \
                                -t jmx/restful-booker/booking.jmx \
                                -l "${RESULTS_DIR}/restful-booker-booking.jtl" \
                                -j "${RESULTS_DIR}/restful-booker-booking.log" \
                                -e -o "${REPORTS_DIR}/restful-booker/" \
                                -Jenvironment=${params.ENVIRONMENT} \
                                ${params.THREADS_OVERRIDE ? "-Jthreads=${params.THREADS_OVERRIDE}" : ''} \
                                ${params.ENABLE_OBSERVABILITY ? '-Jinfluxdb_url=http://localhost:8086/write?db=jmeter' : ''}
                        """
                    }
                }

                stage('RB: Concurrent Update') {
                    steps {
                        sh """
                            rm -f "${RESULTS_DIR}/restful-booker-concurrent.jtl"
                            "${JMETER_BIN}" -n \
                                -t jmx/restful-booker/concurrent-update.jmx \
                                -l "${RESULTS_DIR}/restful-booker-concurrent.jtl" \
                                -j "${RESULTS_DIR}/restful-booker-concurrent.log" \
                                -Jenvironment=${params.ENVIRONMENT} \
                                ${params.ENABLE_OBSERVABILITY ? '-Jinfluxdb_url=http://localhost:8086/write?db=jmeter' : ''}
                        """
                    }
                }
            }
        }

        // ────────────────────────────────────────────
        // DummyJSON Tests
        // ────────────────────────────────────────────
        stage('DummyJSON Tests') {
            when {
                expression {
                    params.TEST_SUITE == 'all' || params.TEST_SUITE == 'dummyjson'
                }
            }
            stages {
                stage('DJ: Login Spike') {
                    steps {
                        sh """
                            rm -f "${RESULTS_DIR}/dummyjson-login.jtl"
                            "${JMETER_BIN}" -n \
                                -t jmx/dummyjson/login.jmx \
                                -l "${RESULTS_DIR}/dummyjson-login.jtl" \
                                -j "${RESULTS_DIR}/dummyjson-login.log" \
                                -Jenvironment=${params.ENVIRONMENT} \
                                ${params.ENABLE_OBSERVABILITY ? '-Jinfluxdb_url=http://localhost:8086/write?db=jmeter' : ''}
                        """
                    }
                }

                stage('DJ: Post Load') {
                    steps {
                        sh """
                            rm -f "${RESULTS_DIR}/dummyjson-postload.jtl"
                            rm -rf "${REPORTS_DIR}/dummyjson/"*
                            "${JMETER_BIN}" -n \
                                -t jmx/dummyjson/post-load.jmx \
                                -l "${RESULTS_DIR}/dummyjson-postload.jtl" \
                                -j "${RESULTS_DIR}/dummyjson-postload.log" \
                                -e -o "${REPORTS_DIR}/dummyjson/" \
                                -Jenvironment=${params.ENVIRONMENT} \
                                ${params.THREADS_OVERRIDE ? "-Jthreads=${params.THREADS_OVERRIDE}" : ''} \
                                ${params.ENABLE_OBSERVABILITY ? '-Jinfluxdb_url=http://localhost:8086/write?db=jmeter' : ''}
                        """
                    }
                }
            }
        }

        // ────────────────────────────────────────────
        // Threshold Validation
        // ────────────────────────────────────────────
        stage('Validate Thresholds') {
            when {
                expression { !params.SKIP_THRESHOLDS }
            }
            steps {
                sh """
                    python3 scripts/check_thresholds.py \
                        --results "${RESULTS_DIR}/" \
                        --config config/thresholds.properties \
                        --environment ${params.ENVIRONMENT} \
                        --env-config config/environments.properties
                """
            }
        }

        // ────────────────────────────────────────────
        // Trend Analysis
        // ────────────────────────────────────────────
        stage('Trend Analysis') {
            steps {
                sh """
                    mkdir -p "${RESULTS_DIR}/trend_history"
                    python3 scripts/trend_report.py \
                        --current "${RESULTS_DIR}/" \
                        --history "${RESULTS_DIR}/trend_history/" || true
                """
            }
        }
    }

    // ────────────────────────────────────────────────
    // Post-build Actions
    // ────────────────────────────────────────────────
    post {
        always {
            // Tear down the observability stack if it was started
            script {
                if (params.ENABLE_OBSERVABILITY) {
                    sh 'docker compose -f docker/docker-compose.yml down -v || true'
                }
            }

            // Archive HTML reports
            publishHTML(target: [
                reportDir:   'reports/restful-booker',
                reportFiles: 'index.html',
                reportName:  'Restful-Booker Performance Report',
                keepAll:     true,
                allowMissing: true
            ])

            publishHTML(target: [
                reportDir:   'reports/dummyjson',
                reportFiles: 'index.html',
                reportName:  'DummyJSON Performance Report',
                keepAll:     true,
                allowMissing: true
            ])

            // Archive raw results
            archiveArtifacts(
                artifacts: 'results/**/*.jtl, results/**/*.log',
                fingerprint: true,
                allowEmptyArchive: true
            )

            // Performance plugin (optional — requires Performance Plugin installed)
            // perfReport(
            //     sourceDataFiles: 'results/**/*.jtl',
            //     errorUnstableThreshold: 1,
            //     errorFailedThreshold: 5,
            //     compareBuildPrevious: true
            // )
        }

        success {
            echo '✅ Performance tests PASSED — all thresholds within limits.'
        }

        failure {
            echo '❌ Performance tests FAILED — threshold breach detected.'

            // Uncomment to enable Slack notification:
            // slackSend(
            //     channel: '#perf-alerts',
            //     color: 'danger',
            //     message: "⚠️ Perf tests failed on build #${BUILD_NUMBER}\n${BUILD_URL}"
            // )
        }

        unstable {
            echo '⚠️ Performance tests completed with warnings.'
        }

        cleanup {
            cleanWs(notFailBuild: true)
        }
    }
}