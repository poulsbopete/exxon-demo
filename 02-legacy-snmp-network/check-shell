#!/usr/bin/env bash
# =============================================================================
# Challenge 2 Check Script — Instruqt automatic validation
# =============================================================================
set -euo pipefail

ES_URL="http://localhost:9200"
CMDB_INDEX="exxon-cmdb-devices"
TRAP_INDEX="logs-snmp.trap-exxon"

fail() {
    echo "INSTRUQT_FAIL_MESSAGE=$*"
    exit 1
}

CMDB_COUNT=$(curl -sf "${ES_URL}/${CMDB_INDEX}/_count" 2>/dev/null | \
    python3 -c "import sys,json; print(json.load(sys.stdin).get('count',0))" 2>/dev/null || echo 0)
[[ ${CMDB_COUNT} -ge 12 ]] || \
    fail "CMDB index missing or incomplete (${CMDB_COUNT}/12 records). Run load-cmdb-data.sh."

TRAP_COUNT=$(curl -sf "${ES_URL}/${TRAP_INDEX}/_count" 2>/dev/null | \
    python3 -c "import sys,json; print(json.load(sys.stdin).get('count',0))" 2>/dev/null || echo 0)
[[ ${TRAP_COUNT} -ge 3 ]] || \
    fail "Not enough SNMP trap data (${TRAP_COUNT} events, need ≥ 3). Run send-snmp-traps.sh."

SITES=$(curl -sf "${ES_URL}/${TRAP_INDEX}/_search" 2>/dev/null | \
    python3 -c "
import sys, json
data = json.load(sys.stdin)
hits = data.get('hits',{}).get('hits',[])
sites = set(h['_source'].get('network.site','') for h in hits if h['_source'].get('event.type') == 'linkDown' and h['_source'].get('network.site'))
print(len(sites))
" 2>/dev/null || echo 0)
[[ ${SITES} -ge 2 ]] || \
    fail "linkDown events only from ${SITES} site(s); need ≥ 2. Run send-snmp-traps.sh."

echo "Challenge 2 validated: ${TRAP_COUNT} SNMP traps ingested across ${SITES} sites."
exit 0
