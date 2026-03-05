#!/usr/bin/env bash
# =============================================================================
# Challenge 1 Check Script — Instruqt automatic validation
# Instruqt calls this script when the user clicks "Check".
# Exit 0 = pass, Exit 1 = fail (with INSTRUQT_FAIL_MESSAGE set).
# =============================================================================
set -euo pipefail

WORK_DIR="/root/exxon-otel"
QUERY_URL="http://localhost:5601/query/unified"

fail() {
    echo "INSTRUQT_FAIL_MESSAGE=$*"
    exit 1
}

# Verify the mock endpoint is reachable
RESULT=$(curl -sf "${QUERY_URL}" 2>/dev/null) || \
    fail "The mock Elastic endpoint is not responding. Run generate-telemetry.sh first."

# Check for at least 1 service in each signal type
TRACES_SVC=$(echo "${RESULT}"  | jq '[.results[] | select(.signals | contains(["traces"]))] | length')
METRICS_SVC=$(echo "${RESULT}" | jq '[.results[] | select(.signals | contains(["metrics"]))] | length')
LOGS_SVC=$(echo "${RESULT}"    | jq '[.results[] | select(.signals | contains(["logs"]))] | length')

[[ ${TRACES_SVC}  -ge 1 ]] || fail "No trace data found. Run generate-telemetry.sh and ensure it completes without errors."
[[ ${METRICS_SVC} -ge 1 ]] || fail "No metrics data found. Check that the metrics pipeline ran (look for 'Sending metrics' output)."
[[ ${LOGS_SVC}    -ge 1 ]] || fail "No log data found. Check that the logs pipeline ran."

# Verify unified tag — at least one service.name appears in both traces AND metrics
UNIFIED=$(echo "${RESULT}" | jq '[.results[] | select((.signals | contains(["traces"])) and (.signals | contains(["metrics"])))] | length')
[[ ${UNIFIED} -ge 1 ]] || \
    fail "service.name does not bridge traces and metrics yet. Ensure generate-telemetry.sh sent both signal types."

echo "Challenge 1 validated: ${UNIFIED} service(s) with unified service.name across traces and metrics."
exit 0
