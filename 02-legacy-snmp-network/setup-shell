#!/usr/bin/env bash
# =============================================================================
# Challenge 2 Setup — Legacy Network Infrastructure (SNMP)
# Exxon Infrastructure 2.0 Demo — Elastic Serverless
# =============================================================================
set -euo pipefail

WORK_DIR="/root/exxon-snmp"
LOG_DIR="/var/log/exxon-demo"
MOCK_ES_PORT=9200

info()  { echo "[INFO]  $*"; }
ok()    { echo "[OK]    $*"; }
warn()  { echo "[WARN]  $*"; }
die()   { echo "[ERROR] $*" >&2; exit 1; }

# -----------------------------------------------------------------------------
# 1. Create directories
# -----------------------------------------------------------------------------
info "Creating working directories..."
mkdir -p "${WORK_DIR}/queries"
mkdir -p "${LOG_DIR}"
ok "Directories created"

# -----------------------------------------------------------------------------
# 2. Write mock Elasticsearch endpoint (port 9200)
#    Stores documents in memory and on disk; handles _count, _search, _bulk
# -----------------------------------------------------------------------------
info "Writing mock Elasticsearch endpoint (port ${MOCK_ES_PORT})..."
cat > /root/mock-elasticsearch.py << 'PYEOF'
#!/usr/bin/env python3
"""
Minimal mock Elasticsearch-compatible HTTP server for Challenge 2.
Supports: POST /{index}/_doc, POST /_bulk, GET /{index}/_count, GET /{index}/_search
"""
import http.server, json, os, threading
from datetime import datetime
from collections import defaultdict

LOG_DIR = "/var/log/exxon-demo"
os.makedirs(LOG_DIR, exist_ok=True)

store = defaultdict(list)  # index -> list of documents
lock  = threading.Lock()

def parse_index(path):
    parts = [p for p in path.strip("/").split("/") if p]
    return parts[0] if parts else "default"

class ESHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parts = [p for p in self.path.strip("/").split("/") if p]
        if len(parts) >= 2 and parts[-1] == "_count":
            idx = parts[0]
            with lock:
                count = len(store.get(idx, []))
            self._json(200, {"count": count, "_shards": {"total": 1, "successful": 1}})
        elif len(parts) >= 2 and parts[-1] == "_search":
            idx = parts[0]
            with lock:
                docs = store.get(idx, [])
            hits = [{"_source": d} for d in docs[:100]]
            self._json(200, {"hits": {"total": {"value": len(docs)}, "hits": hits}})
        elif self.path == "/_cluster/health":
            self._json(200, {"status": "green", "cluster_name": "mock-elastic"})
        else:
            self._json(200, {"acknowledged": True})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8", errors="replace")
        parts = [p for p in self.path.strip("/").split("/") if p]

        if "_bulk" in parts:
            lines = [l for l in body.split("\n") if l.strip()]
            count = 0
            i = 0
            while i < len(lines) - 1:
                try:
                    action = json.loads(lines[i])
                    doc    = json.loads(lines[i+1])
                    idx = list(action.values())[0].get("_index", "bulk-default")
                    doc["@timestamp"] = datetime.utcnow().isoformat() + "Z"
                    with lock:
                        store[idx].append(doc)
                    count += 1
                    i += 2
                except Exception:
                    i += 1
            self._json(200, {"items": [{"index": {"result": "created"}} for _ in range(count)], "errors": False})
        elif len(parts) >= 2 and parts[-1] == "_doc":
            idx = parts[0]
            try:
                doc = json.loads(body)
            except Exception:
                doc = {}
            doc["@timestamp"] = datetime.utcnow().isoformat() + "Z"
            with lock:
                store[idx].append(doc)
            self._json(201, {"result": "created", "_index": idx})
        else:
            self._json(200, {"acknowledged": True})

    def _json(self, code, data):
        payload = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt, *args):
        print(f"[ES]  {self.path}  {args[1] if len(args)>1 else ''}")

if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9200
    print(f"[INFO] Mock Elasticsearch listening on :{port}")
    http.server.HTTPServer(("0.0.0.0", port), ESHandler).serve_forever()
PYEOF
chmod +x /root/mock-elasticsearch.py

# Start if not already running from Challenge 1 (port may already be up)
if ! curl -sf "http://localhost:${MOCK_ES_PORT}/_cluster/health" >/dev/null 2>&1; then
    pkill -f "mock-elasticsearch.py" 2>/dev/null || true
    nohup python3 /root/mock-elasticsearch.py "${MOCK_ES_PORT}" > "${LOG_DIR}/mock-es.log" 2>&1 &
    sleep 2
    curl -sf "http://localhost:${MOCK_ES_PORT}/_cluster/health" >/dev/null 2>&1 || \
        die "Mock Elasticsearch failed to start. Check ${LOG_DIR}/mock-es.log"
fi
ok "Mock Elasticsearch running on port ${MOCK_ES_PORT}"

# -----------------------------------------------------------------------------
# 3. Write sample SNMP traps file
# -----------------------------------------------------------------------------
info "Writing sample SNMP trap data..."
cat > "${WORK_DIR}/sample-traps.txt" << 'TRAPEOF'
# =============================================================================
# Simulated Cisco SNMP v2c Traps — Exxon WAN Infrastructure
# Format: SNMPv2-TRAP timestamp enterprise community [varbinds]
# These are the raw traps OpenNMS receives today — invisible to the app team.
# =============================================================================

2026-03-05T08:14:22Z UDP: [10.52.1.1]:1620 -> [10.52.0.10]:1620
  OID: .1.3.6.1.6.3.1.1.5.3          ; linkDown
  .1.3.6.1.2.1.1.5.0 = cisco-sw-houston-01
  .1.3.6.1.2.1.2.2.1.1.47 = INTEGER: 47   ; ifIndex GigabitEthernet0/47
  .1.3.6.1.2.1.2.2.1.8.47 = INTEGER: 2    ; ifOperStatus = down
  Community: exxon-public

2026-03-05T08:14:35Z UDP: [10.52.2.3]:1620 -> [10.52.0.10]:1620
  OID: .1.3.6.1.6.3.1.1.5.3          ; linkDown
  .1.3.6.1.2.1.1.5.0 = cisco-sw-midland-03
  .1.3.6.1.2.1.2.2.1.1.1  = INTEGER: 1    ; TenGigabitEthernet1/0/1
  .1.3.6.1.2.1.2.2.1.8.1  = INTEGER: 2    ; ifOperStatus = down
  Community: exxon-public

2026-03-05T08:15:01Z UDP: [10.52.1.1]:1620 -> [10.52.0.10]:1620
  OID: .1.3.6.1.6.3.1.1.5.4          ; linkUp  (recovery)
  .1.3.6.1.2.1.1.5.0 = cisco-sw-houston-01
  .1.3.6.1.2.1.2.2.1.1.47 = INTEGER: 47
  .1.3.6.1.2.1.2.2.1.8.47 = INTEGER: 1    ; ifOperStatus = up
  Community: exxon-public

2026-03-05T08:15:47Z UDP: [10.52.3.7]:1620 -> [10.52.0.10]:1620
  OID: .1.3.6.1.6.3.1.1.5.3          ; linkDown
  .1.3.6.1.2.1.1.5.0 = cisco-sw-corpus-02
  .1.3.6.1.2.1.2.2.1.1.23 = INTEGER: 23
  .1.3.6.1.2.1.2.2.1.8.23 = INTEGER: 2    ; ifOperStatus = down
  Community: exxon-public

2026-03-05T08:16:03Z UDP: [10.52.1.1]:1620 -> [10.52.0.10]:1620
  OID: .1.3.6.1.6.3.1.1.5.3          ; linkDown  (second flap!)
  .1.3.6.1.2.1.1.5.0 = cisco-sw-houston-01
  .1.3.6.1.2.1.2.2.1.1.47 = INTEGER: 47
  .1.3.6.1.2.1.2.2.1.8.47 = INTEGER: 2
  Community: exxon-public
TRAPEOF
ok "Sample SNMP trap data written"

# -----------------------------------------------------------------------------
# 4. Write Elastic Agent SNMP integration config
# -----------------------------------------------------------------------------
info "Writing Elastic Agent SNMP integration config..."
cat > "${WORK_DIR}/elastic-agent-snmp.yml" << 'AGENTEOF'
# =============================================================================
# Elastic Agent — Network SNMP Integration Configuration
# Replaces OpenNMS as the SNMP trap receiver for Exxon WAN infrastructure.
#
# In production: deploy Elastic Agent on the OpenNMS host (or replace it),
# point this config at your Elastic Serverless OTLP/ES endpoint, and the
# SNMP integration handles MIB translation automatically.
# =============================================================================

inputs:
  - type: snmp
    streams:
      - metricsets: ["trap"]
        listen_address: "0.0.0.0:1620"
        community: "exxon-public"
        version: 2c

        # OID translation — Elastic bundles common Cisco MIBs
        translate_oids: true
        include_mib_files:
          - CISCO-PRODUCTS-MIB
          - IF-MIB
          - SNMPv2-MIB

        # Add Exxon-specific metadata to every trap document
        fields:
          network.environment: "exxon-wan-infrastructure"
          organization: "exxon-infrastructure-2.0"
          ingest.source: "elastic-snmp-integration"

        # Enrich policy joins device.hostname → ServiceNow CMDB data
        processors:
          - enrich:
              policy_name: "exxon-cmdb-enrich"
              field: "snmp.system.name"   # sysDescr from trap
              target_field: "cmdb"
              ignore_missing: true

output.elasticsearch:
  hosts: ["localhost:9200"]
  index: "logs-snmp.trap-exxon"
  # In production:
  # cloud_id: "<your-elastic-cloud-id>"
  # api_key:  "<your-elastic-api-key>"
AGENTEOF
ok "Elastic Agent SNMP config written"

# -----------------------------------------------------------------------------
# 5. Write ServiceNow CMDB mock data loader
# -----------------------------------------------------------------------------
info "Writing CMDB data loader..."
cat > "${WORK_DIR}/load-cmdb-data.sh" << 'CMDBEOF'
#!/usr/bin/env bash
# Loads 12 Exxon network device records into mock Elasticsearch
# Simulates a ServiceNow CMDB export enriched with ThousandEyes agent IDs
set -euo pipefail

ES_URL="http://localhost:9200"
INDEX="exxon-cmdb-devices"

DEVICES=(
    '{"device.hostname":"cisco-sw-houston-01","network.site":"Houston-Refinery-Campus","application.owner":"exxon-infrastructure-2.0-team","business.service":"Upstream-Operations","thousandeyes.agent_id":"TE-HOU-001","network.region":"south-tx"}'
    '{"device.hostname":"cisco-sw-houston-02","network.site":"Houston-Refinery-Campus","application.owner":"exxon-infrastructure-2.0-team","business.service":"Upstream-Operations","thousandeyes.agent_id":"TE-HOU-002","network.region":"south-tx"}'
    '{"device.hostname":"cisco-sw-midland-01","network.site":"Midland-Field-Ops","application.owner":"upstream-operations-team","business.service":"Field-Data-Collection","thousandeyes.agent_id":"TE-MID-001","network.region":"west-tx"}'
    '{"device.hostname":"cisco-sw-midland-02","network.site":"Midland-Field-Ops","application.owner":"upstream-operations-team","business.service":"Field-Data-Collection","thousandeyes.agent_id":"TE-MID-002","network.region":"west-tx"}'
    '{"device.hostname":"cisco-sw-midland-03","network.site":"Midland-Field-Ops","application.owner":"upstream-operations-team","business.service":"Field-Data-Collection","thousandeyes.agent_id":"TE-MID-003","network.region":"west-tx"}'
    '{"device.hostname":"cisco-sw-corpus-01","network.site":"Corpus-Christi-Refinery","application.owner":"downstream-logistics-team","business.service":"Pipeline-Monitoring","thousandeyes.agent_id":"TE-CRP-001","network.region":"gulf-coast"}'
    '{"device.hostname":"cisco-sw-corpus-02","network.site":"Corpus-Christi-Refinery","application.owner":"downstream-logistics-team","business.service":"Pipeline-Monitoring","thousandeyes.agent_id":"TE-CRP-002","network.region":"gulf-coast"}'
    '{"device.hostname":"cisco-sw-baytown-01","network.site":"Baytown-Chemical-Plant","application.owner":"chemical-ops-team","business.service":"Process-Control","thousandeyes.agent_id":"TE-BAY-001","network.region":"gulf-coast"}'
    '{"device.hostname":"cisco-sw-beaumont-01","network.site":"Beaumont-Refinery","application.owner":"refinery-ops-team","business.service":"Refinery-Control","thousandeyes.agent_id":"TE-BEA-001","network.region":"gulf-coast"}'
    '{"device.hostname":"cisco-core-houston-01","network.site":"Houston-DC-Primary","application.owner":"network-core-team","business.service":"Core-Infrastructure","thousandeyes.agent_id":"TE-DC-001","network.region":"south-tx"}'
    '{"device.hostname":"cisco-core-dallas-01","network.site":"Dallas-DC-Secondary","application.owner":"network-core-team","business.service":"Core-Infrastructure","thousandeyes.agent_id":"TE-DAL-001","network.region":"north-tx"}'
    '{"device.hostname":"cisco-edge-azure-01","network.site":"Azure-ExpressRoute-Edge","application.owner":"cloud-networking-team","business.service":"Azure-Connectivity","thousandeyes.agent_id":"TE-AZ-001","network.region":"azure-southcentralus"}'
)

echo "Loading ${#DEVICES[@]} CMDB device records into ${INDEX}..."
for device in "${DEVICES[@]}"; do
    hostname=$(echo "${device}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('device.hostname','unknown'))")
    curl -sf -X POST "${ES_URL}/${INDEX}/_doc" \
        -H "Content-Type: application/json" \
        -d "${device}" > /dev/null
    echo "  [OK] ${hostname}"
done

COUNT=$(curl -sf "${ES_URL}/${INDEX}/_count" | python3 -c "import sys,json; print(json.load(sys.stdin).get('count',0))")
echo ""
echo "✓ CMDB index loaded → ${COUNT} device records in ${INDEX}"
CMDBEOF
chmod +x "${WORK_DIR}/load-cmdb-data.sh"
ok "CMDB loader written"

# -----------------------------------------------------------------------------
# 6. Write SNMP trap sender (simulates snmptrapd relay → Elastic)
# -----------------------------------------------------------------------------
info "Writing SNMP trap sender..."
cat > "${WORK_DIR}/send-snmp-traps.sh" << 'TRAPEOF'
#!/usr/bin/env bash
# =============================================================================
# Simulates SNMP v2c trap relay to mock Elastic SNMP integration receiver.
# In production, Elastic Agent (snmp input) receives these directly via UDP.
# Here we POST equivalent JSON documents to the mock Elasticsearch endpoint.
# =============================================================================
set -euo pipefail

ES_URL="http://localhost:9200"
INDEX="logs-snmp.trap-exxon"

declare -A SITES=(
    ["cisco-sw-houston-01"]="Houston-Refinery-Campus"
    ["cisco-sw-midland-03"]="Midland-Field-Ops"
    ["cisco-sw-corpus-02"]="Corpus-Christi-Refinery"
)

declare -A OWNERS=(
    ["cisco-sw-houston-01"]="exxon-infrastructure-2.0-team"
    ["cisco-sw-midland-03"]="upstream-operations-team"
    ["cisco-sw-corpus-02"]="downstream-logistics-team"
)

declare -A INTERFACES=(
    ["cisco-sw-houston-01"]="GigabitEthernet0/47"
    ["cisco-sw-midland-03"]="TenGigabitEthernet1/0/1"
    ["cisco-sw-corpus-02"]="GigabitEthernet0/23"
)

send_trap() {
    local hostname="$1"
    local status="$2"   # "down" or "up"
    local site="${SITES[$hostname]}"
    local owner="${OWNERS[$hostname]}"
    local iface="${INTERFACES[$hostname]}"
    local oper_status=$( [[ "$status" == "down" ]] && echo 2 || echo 1 )
    local trap_oid=$( [[ "$status" == "down" ]] && echo ".1.3.6.1.6.3.1.1.5.3" || echo ".1.3.6.1.6.3.1.1.5.4" )
    local trap_name=$( [[ "$status" == "down" ]] && echo "linkDown" || echo "linkUp" )

    curl -sf -X POST "${ES_URL}/${INDEX}/_doc" \
        -H "Content-Type: application/json" \
        -d "{
  \"@timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",
  \"event.type\": \"${trap_name}\",
  \"event.category\": \"network\",
  \"snmp.trap.oid\": \"${trap_oid}\",
  \"snmp.system.name\": \"${hostname}\",
  \"snmp.interface.index\": \"${iface}\",
  \"snmp.interface.oper_status\": ${oper_status},
  \"snmp.community\": \"exxon-public\",
  \"snmp.version\": \"2c\",
  \"network.site\": \"${site}\",
  \"application.owner\": \"${owner}\",
  \"network.environment\": \"exxon-wan-infrastructure\",
  \"organization\": \"exxon-infrastructure-2.0\",
  \"ingest.source\": \"elastic-snmp-integration\"
}" > /dev/null

    local arrow=$( [[ "$status" == "down" ]] && echo "↓" || echo "↑" )
    echo "[INFO] Sending ${trap_name} trap ${arrow} ${hostname} (${iface}) → site: ${site}"
}

echo "============================================================"
echo "  Exxon SNMP Trap Generator"
echo "  Simulating: Cisco WAN infrastructure link events"
echo "  Target: ${ES_URL}/${INDEX}"
echo "============================================================"

# Simulate the circuit flapping scenario from the sample-traps.txt
send_trap "cisco-sw-houston-01" "down"
sleep 0.3
send_trap "cisco-sw-midland-03" "down"
sleep 0.3
send_trap "cisco-sw-houston-01" "up"
sleep 0.3
send_trap "cisco-sw-corpus-02"  "down"
sleep 0.3
send_trap "cisco-sw-houston-01" "down"   # second flap

echo ""
echo "Traps sent. Verify count with:"
echo "  curl -s http://localhost:9200/${INDEX}/_count | jq ."
TRAPEOF
chmod +x "${WORK_DIR}/send-snmp-traps.sh"
ok "SNMP trap sender written"

# -----------------------------------------------------------------------------
# 7. Write ES|QL queries
# -----------------------------------------------------------------------------
info "Writing ES|QL network impact query..."
cat > "${WORK_DIR}/queries/network-impact.esql" << 'ESQLEOF'
// =============================================================================
// Exxon Network Impact Query — ES|QL
// Identifies which application teams are impacted by current link-down events.
// Uses CMDB enrichment to map device hostname → site → application owner.
//
// Run in Kibana Dev Tools or the ES|QL console.
// =============================================================================
FROM logs-snmp.trap-exxon METADATA _index
| WHERE @timestamp > NOW() - 30 minutes
| WHERE event.type == "linkDown"
| STATS
    link_down_count      = COUNT(*),
    affected_interfaces  = VALUES(snmp.interface.index),
    last_event           = MAX(@timestamp)
  BY network.site, application.owner
| SORT link_down_count DESC
ESQLEOF

cat > "${WORK_DIR}/queries/thousandeyes-correlation.esql" << 'ESQLEOF'
// =============================================================================
// ThousandEyes Correlation Query — ES|QL
// Correlates SNMP linkDown events with ThousandEyes circuit metrics.
// In a full Elastic Serverless deployment, logs-thousandeyes.* is populated
// by the Elastic ThousandEyes integration.
//
// This demo simulates the join using the mock CMDB thousandeyes.agent_id field.
// =============================================================================
FROM logs-snmp.trap-exxon METADATA _index
| WHERE @timestamp > NOW() - 30 minutes
| WHERE event.type == "linkDown"
| EVAL thousandeyes_agent_id = CASE(
    network.site == "Houston-Refinery-Campus", "TE-HOU-001",
    network.site == "Midland-Field-Ops",        "TE-MID-003",
    network.site == "Corpus-Christi-Refinery",  "TE-CRP-002",
    "UNKNOWN"
  )
| EVAL simulated_packet_loss_pct = CASE(
    network.site == "Houston-Refinery-Campus", 12.4,
    network.site == "Midland-Field-Ops",        3.1,
    network.site == "Corpus-Christi-Refinery",  0.8,
    0.0
  )
| EVAL simulated_jitter_ms = CASE(
    network.site == "Houston-Refinery-Campus", 47.2,
    network.site == "Midland-Field-Ops",        8.9,
    network.site == "Corpus-Christi-Refinery",  2.1,
    0.0
  )
| STATS
    link_events        = COUNT(*),
    max_packet_loss    = MAX(simulated_packet_loss_pct),
    max_jitter_ms      = MAX(simulated_jitter_ms),
    te_agent           = FIRST(thousandeyes_agent_id)
  BY network.site, application.owner
| SORT max_packet_loss DESC
ESQLEOF
ok "ES|QL queries written"

# -----------------------------------------------------------------------------
# 8. Write validation script
# -----------------------------------------------------------------------------
info "Writing validation script..."
cat > "${WORK_DIR}/check-snmp-ingest.sh" << 'CHECKEOF'
#!/usr/bin/env bash
set -euo pipefail

ES_URL="http://localhost:9200"
CMDB_INDEX="exxon-cmdb-devices"
TRAP_INDEX="logs-snmp.trap-exxon"
PASS=0
FAIL=0

check() {
    local desc="$1"
    local condition="$2"
    if eval "${condition}"; then
        echo "✓ ${desc}"
        PASS=$(( PASS + 1 ))
    else
        echo "✗ ${desc}"
        FAIL=$(( FAIL + 1 ))
    fi
}

echo ""
echo "========================================="
echo "  Challenge 2 Validation"
echo "========================================="

CMDB_COUNT=$(curl -sf "${ES_URL}/${CMDB_INDEX}/_count" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('count',0))" 2>/dev/null || echo 0)
TRAP_COUNT=$(curl -sf "${ES_URL}/${TRAP_INDEX}/_count"  2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('count',0))" 2>/dev/null || echo 0)

check "CMDB index loaded                → ${CMDB_COUNT} device records (expect 12)" "[[ ${CMDB_COUNT} -ge 12 ]]"
check "SNMP trap data received          → ${TRAP_COUNT} trap events ingested"       "[[ ${TRAP_COUNT} -ge 3 ]]"

# Verify at least one trap has network.site set (enrichment applied)
ENRICHED=$(curl -sf "${ES_URL}/${TRAP_INDEX}/_search" 2>/dev/null | \
    python3 -c "
import sys, json
data = json.load(sys.stdin)
hits = data.get('hits',{}).get('hits',[])
enriched = [h for h in hits if h.get('_source',{}).get('network.site')]
print(len(enriched))
" 2>/dev/null || echo 0)
check "CMDB enrichment applied          → network.site populated (${ENRICHED} docs)" "[[ ${ENRICHED} -ge 1 ]]"

# Verify linkDown events for at least 2 different sites
SITES=$(curl -sf "${ES_URL}/${TRAP_INDEX}/_search" 2>/dev/null | \
    python3 -c "
import sys, json
data = json.load(sys.stdin)
hits = data.get('hits',{}).get('hits',[])
sites = set(h['_source'].get('network.site','') for h in hits if h['_source'].get('event.type') == 'linkDown' and h['_source'].get('network.site'))
print(len(sites))
" 2>/dev/null || echo 0)
check "Multi-site link-down events      → ${SITES} site(s) affected (expect ≥ 2)" "[[ ${SITES} -ge 2 ]]"

echo ""
if [[ ${FAIL} -eq 0 ]]; then
    echo "✓ Challenge 2 complete — SNMP tamed, network events visible to app teams"
    exit 0
else
    echo "✗ ${FAIL} check(s) failed."
    echo "  Run ./load-cmdb-data.sh then ./send-snmp-traps.sh and try again."
    exit 1
fi
CHECKEOF
chmod +x "${WORK_DIR}/check-snmp-ingest.sh"
ok "Validation script written"

# -----------------------------------------------------------------------------
# 9. Pre-load CMDB data
# -----------------------------------------------------------------------------
info "Pre-loading CMDB data..."
bash "${WORK_DIR}/load-cmdb-data.sh" > "${LOG_DIR}/cmdb-load.log" 2>&1 || \
    warn "CMDB pre-load had warnings (check ${LOG_DIR}/cmdb-load.log)"
ok "CMDB data pre-loaded"

# -----------------------------------------------------------------------------
# Done
# -----------------------------------------------------------------------------
echo ""
echo "================================================================"
echo "  Challenge 2 environment ready."
echo "  Working directory  : ${WORK_DIR}"
echo "  Mock Elasticsearch : http://localhost:${MOCK_ES_PORT}"
echo "  CMDB loader        : ${WORK_DIR}/load-cmdb-data.sh"
echo "  SNMP trap sender   : ${WORK_DIR}/send-snmp-traps.sh"
echo "  Validate           : ${WORK_DIR}/check-snmp-ingest.sh"
echo "================================================================"
