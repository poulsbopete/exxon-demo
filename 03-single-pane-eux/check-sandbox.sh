#!/usr/bin/env bash
# =============================================================================
# Challenge 3 Check Script — Instruqt automatic validation
# =============================================================================
set -euo pipefail

WORK_DIR="/root/exxon-eux"

fail() {
    echo "INSTRUQT_FAIL_MESSAGE=$*"
    exit 1
}

[[ -f "${WORK_DIR}/data/avd-metrics.json" ]] || \
    fail "AVD metrics data not found. Has the environment finished loading?"

[[ -f "${WORK_DIR}/data/appgate-audit.json" ]] || \
    fail "AppGate audit data not found."

BLOCKED=$(python3 -c "
import json
with open('${WORK_DIR}/data/iboss-connections.json') as f:
    data = [json.loads(l) for l in f if l.strip()]
print(len([d for d in data if d.get('user.name')=='jsmith' and d.get('event.outcome')=='blocked']))
" 2>/dev/null || echo 0)
[[ ${BLOCKED} -ge 2 ]] || \
    fail "iboss blocked events not found for jsmith (${BLOCKED} found, need ≥ 2)."

ROOT_CAUSE=$(python3 "${WORK_DIR}/investigate.py" --full-report --user jsmith 2>/dev/null | grep "ROOT CAUSE:" | awk '{print $NF}')
[[ -n "${ROOT_CAUSE}" && "${ROOT_CAUSE}" != "UNKNOWN" ]] || \
    fail "Could not determine root cause. Run: python3 ${WORK_DIR}/investigate.py --full-report --user jsmith"

echo "Challenge 3 validated: root cause identified as ${ROOT_CAUSE}."
exit 0
