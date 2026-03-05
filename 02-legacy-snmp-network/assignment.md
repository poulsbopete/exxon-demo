---
slug: legacy-snmp-network
id: h5f8ewkl75xh
type: challenge
title: 'Challenge 2: Taming Legacy Network Infrastructure (SNMP)'
teaser: Stop treating Cisco SNMP traps as an island. Ingest legacy SNMP v2c traps
  and enrich them with ServiceNow CMDB data so network events show up in the same
  Elastic platform as your modern APM.
notes:
- type: text
  contents: |
    Exxon's network team monitors Cisco switches and routers via **OpenNMS**
    receiving SNMP v2c traps and polling MIB OIDs. These network events —
    link flaps, interface errors, BGP state changes — are completely
    invisible to the application teams watching Datadog.

    ThousandEyes agents on Cisco switches provide circuit-level visibility,
    but again in isolation. When a circuit flaps, the WAN team knows, but
    the app team doesn't — "it's very disjointed."
- type: text
  contents: |
    The **Elastic Network SNMP integration** listens for UDP SNMP traps and
    translates OID values into human-readable field names using bundled MIB
    files. **Runtime fields** and **enrich policies** let you join incoming
    trap data with a ServiceNow CMDB index at query time — no ETL required.
- type: text
  contents: |
    **SNMP via OTel Collector — how it works:**

    Modern OTel Collectors ship a native `snmpreceiver` that polls MIB OIDs
    and receives v1/v2c/v3 traps, then exports them as **OpenTelemetry
    metrics and logs** directly to Elastic Serverless:

    ```
    Cisco Switch (UDP :162)
         │  SNMP v2c trap
         ▼
    OTel Collector (snmpreceiver)
         │  translate OID → human field
         ▼
    Elastic OTLP endpoint
         │
         ├─ network.interface.errors   → Metrics Explorer
         ├─ network.device.status      → Inventory
         └─ snmp.trap.linkDown         → Logs / Alerts
    ```

    No OpenNMS required. No separate SNMP proxy. One collector binary.
- type: text
  contents: |
    **SNMP trap → ServiceNow CMDB enrichment in Elastic:**

    When a `linkDown` trap arrives from IP `10.12.5.22`, Elastic's
    **enrich processor** automatically looks up that IP in a CMDB index
    (synced from ServiceNow) and stamps the event with:

    - `cmdb.asset_tag`: CHG0043891
    - `cmdb.location`: Permian Basin — Rack C4
    - `cmdb.owner_team`: WAN Engineering
    - `cmdb.ci_class`: Cisco Catalyst 9300

    The NOC sees *which switch, where, owned by whom* — without a
    separate CMDB lookup ticket.
- type: text
  contents: |
    **OpenNMS vs. Elastic for SNMP: Cost comparison**

    OpenNMS Enterprise requires dedicated polling servers, a PostgreSQL
    database, and per-device licensing. Elastic Serverless SNMP:

    - **No polling servers** — OTel Collector runs on any Linux host
    - **No dedicated database** — events land in the same Elasticsearch
      project as APM, logs, and metrics
    - **No per-device license** — ingest is priced by data volume, not
      device count
    - **Correlation built-in** — network events share the same timeline
      as the application events they caused

    For Exxon's estate of **hundreds of Cisco devices**, this eliminates
    an entire tool and its operational overhead.
tabs:
- id: 4lxqmpxckh5p
  title: Terminal
  type: terminal
  hostname: es3-api
- id: zjyfrxv8lhfa
  title: Demo App
  type: service
  hostname: es3-api
  path: /
  port: 8090
- id: 1mwg7lywnkoo
  title: Elastic Serverless
  type: service
  hostname: es3-api
  path: /app/dashboards#/list?_g=(filters:!(),refreshInterval:(pause:!f,value:30000),time:(from:now-30m,to:now))
  port: 8080
  custom_request_headers:
  - key: Content-Security-Policy
    value: 'script-src ''self'' https://kibana.estccdn.com; worker-src blob: ''self'';
      style-src ''unsafe-inline'' ''self'' https://kibana.estccdn.com; style-src-elem
      ''unsafe-inline'' ''self'' https://kibana.estccdn.com'
  custom_response_headers:
  - key: Content-Security-Policy
    value: 'script-src ''self'' https://kibana.estccdn.com; worker-src blob: ''self'';
      style-src ''unsafe-inline'' ''self'' https://kibana.estccdn.com; style-src-elem
      ''unsafe-inline'' ''self'' https://kibana.estccdn.com'
difficulty: intermediate
timelimit: 2400
enhanced_loading: null
---

# Challenge 2: Taming Legacy Network Infrastructure (SNMP)

## The Situation

Exxon's WAN team manages a campus of Cisco switches and routers that emit
**SNMP v2c traps** the moment a link changes state. Today those traps are
swallowed by **OpenNMS** — a tool only the network team can log into. When
circuit flapping begins, the app team is the last to know.

ThousandEyes agents mounted on Cisco switches provide circuit-level visibility,
but again in total isolation. The result: link-down events in the WAN are
correlated to application errors in Splunk/Datadog **manually**, sometimes
hours after the fact.

> **Goal:** Ingest Cisco SNMP traps into Elastic Serverless, enrich them with
> ServiceNow CMDB device ownership data, and surface them in the same platform
> as your APM data from Challenge 1.

---

## Step 1 — Review the Simulated SNMP Trap Data

A mock **snmptrapd** process is sending simulated Cisco `linkDown` (OID
`.1.3.6.1.6.3.1.1.5.3`) and `linkUp` (`.1.3.6.1.6.3.1.1.5.4`) traps to
port `1620/UDP` on the sandbox. Review the trap stream:

```bash
cat /root/exxon-snmp/sample-traps.txt
```

Each simulated trap includes:
- `sysDescr` — device hostname (e.g., `cisco-sw-houston-01`)
- `ifIndex` — interface index (e.g., `GigabitEthernet0/47`)
- `ifOperStatus` — `1` (up) or `2` (down)
- `enterprise` OID — Cisco-specific trap enterprise

Notice the format. These are raw SNMP v2c traps — exactly what Exxon's
production OpenNMS is receiving today, but is unable to correlate with
application data.

---

## Step 2 — Review the Elastic SNMP Integration Config

The Elastic **Network SNMP integration** config has been pre-generated at
`/root/exxon-snmp/elastic-agent-snmp.yml`. Open it in the editor tab and
review the key sections:

```bash
cat /root/exxon-snmp/elastic-agent-snmp.yml
```

Key configuration points:

| Parameter | Value | Notes |
|---|---|---|
| `listen_address` | `0.0.0.0:1620` | Receiving UDP traps |
| `community` | `exxon-public` | v2c community string |
| `translate_oids` | `true` | Converts OIDs to readable names |
| `fields.network.site` | dynamic | Populated by enrich policy |
| `output.elasticsearch.hosts` | `localhost:9200` | Mock Elastic endpoint |

---

## Step 3 — Load the ServiceNow CMDB Mock Data

In production, Exxon's ServiceNow CMDB maps every network device to a site,
application owner, and business service. The Elastic **enrich policy** joins
incoming SNMP trap documents to this CMDB data at query time.

Load the mock CMDB records:

```bash
cd /root/exxon-snmp
./load-cmdb-data.sh
```

This script POSTs 12 device records to the mock Elastic endpoint under index
`exxon-cmdb-devices`. Each record has:

```json
{
  "device.hostname": "cisco-sw-houston-01",
  "network.site":    "Houston-Refinery-Campus",
  "application.owner": "exxon-infrastructure-2.0-team",
  "business.service":  "Upstream-Operations",
  "thousandeyes.agent_id": "TE-HOU-001"
}
```

After loading, verify the CMDB index:

```bash
curl -s http://localhost:9200/exxon-cmdb-devices/_count | jq .
```

Expected: `{ "count": 12 }`

---

## Step 4 — Send Simulated SNMP Traps

Run the trap generator to push simulated Cisco link events into the mock
Elastic SNMP integration receiver:

```bash
cd /root/exxon-snmp
./send-snmp-traps.sh
```

You will see output like:

```
[INFO] Sending linkDown trap → cisco-sw-houston-01 (GigabitEthernet0/47) → site: Houston-Refinery-Campus
[INFO] Sending linkDown trap → cisco-sw-midland-03 (TenGigabitEthernet1/0/1) → site: Midland-Field-Ops
[INFO] Sending linkUp   trap → cisco-sw-houston-01 (GigabitEthernet0/47) → (recovered)
[INFO] Sending linkDown trap → cisco-sw-corpus-02 (GigabitEthernet0/23) → site: Corpus-Christi-Refinery
```

> **This is circuit flapping.** Notice `cisco-sw-houston-01` flaps twice.
> In the old world (OpenNMS only), nobody in the app team sees this.

---

## Step 5 — Write the ES|QL Network Impact Query

Now write the query that answers: **"Which application teams are affected by
the current network events?"**

Open the query file:

```bash
cat /root/exxon-snmp/queries/network-impact.esql
```

Review and understand the query. It:
1. Reads from `logs-snmp.trap-*` (SNMP integration output index)
2. Filters for `linkDown` events in the last 30 minutes
3. Enriches with CMDB data (joins on `device.hostname`)
4. Groups by `network.site` and `application.owner`

The expected output:

| network.site | application.owner | link_down_count | affected_interfaces |
|---|---|---|---|
| Houston-Refinery-Campus | exxon-infrastructure-2.0-team | 3 | GigabitEthernet0/47, ... |
| Midland-Field-Ops | upstream-operations-team | 1 | TenGigabitEthernet1/0/1 |
| Corpus-Christi-Refinery | downstream-logistics-team | 1 | GigabitEthernet0/23 |

> **Presenter script:** "Exxon's WAN team already sees this in OpenNMS.
> What's new is that the **app team** now sees it too — in the same Kibana
> instance where they watch their APM traces from Challenge 1. No Slack
> threads. No war room. One platform."

---

## Step 6 — Configure the ThousandEyes Correlation

Exxon has ThousandEyes agents on their Cisco switches. Each CMDB record
includes a `thousandeyes.agent_id` field. Run the correlation query:

```bash
cat /root/exxon-snmp/queries/thousandeyes-correlation.esql
```

This query shows — for every `linkDown` event — the correlated
ThousandEyes circuit-level metrics (packet loss %, jitter ms) that were
active during the same time window. In a full Elastic Serverless deployment,
this pulls from `logs-thousandeyes.*` via the Elastic ThousandEyes integration.

---

## Step 7 — Validate

Run the validation check:

```bash
/root/exxon-snmp/check-snmp-ingest.sh
```

The script verifies:
1. CMDB data is loaded (12 device records)
2. SNMP trap data landed in the mock index
3. At least one trap document has been enriched with `network.site` from CMDB
4. A `linkDown` event exists for at least 2 different sites

Successful output:

```
✓ CMDB index loaded                → 12 device records
✓ SNMP trap data received          → N trap events ingested
✓ CMDB enrichment applied          → network.site populated
✓ Multi-site link-down events      → 3 sites affected
✓ Challenge 2 complete — SNMP tamed, network events visible to app teams
```

---

## Why This Matters for Exxon

| Before (OpenNMS isolated) | After (Elastic Serverless + SNMP integration) |
|---|---|
| Network events visible only in OpenNMS | Network events in same Kibana as APM traces |
| Manual cross-team correlation (hours) | ES|QL joins CMDB + SNMP in milliseconds |
| ThousandEyes data siloed separately | ThousandEyes agent_id links to SNMP events |
| No cost insight across storage engines | Unified retention policy in one platform |

> Continue to Challenge 3 to see how this data, combined with Windows event
> logs and AVD metrics, creates the complete **"How is the machine functioning
> for the user?"** dashboard Exxon needs.
