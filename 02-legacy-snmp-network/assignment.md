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
- id: 5hcn3kt9phei
  title: Demo App
  type: service
  hostname: es3-api
  path: /
  port: 8090
- id: ch2faultinject
  title: Fault Injection
  type: service
  hostname: es3-api
  path: /chaos?deployment_id=exxon
  port: 8090
- id: tpgjkiktcvye
  title: Elastic Serverless
  type: service
  hostname: es3-api
  path: /app/discover
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
difficulty: basic
timelimit: 1800
enhanced_loading: null
---

# Challenge 2: Taming Legacy Network Infrastructure (SNMP)

## The Situation

Exxon's WAN team monitors **hundreds of Cisco switches** at refineries across
Texas — Houston, Midland, Corpus Christi. SNMP traps flow into OpenNMS.
Application teams watch Datadog. **Neither tool can see the other.**

When `cisco-sw-houston-01` flaps its `GigabitEthernet0/47` port, the WAN team
gets an OpenNMS alert. The app team sees API errors spiking — but nobody
connects the two events for 45 minutes.

In this challenge, simulated SNMP traps and ServiceNow CMDB records have been
loaded into your Elastic Serverless project automatically. Your task: explore
this data and see how Elastic unifies the network and application layers.

---

## Step 1 — Trigger a Fault

Switch to the **Fault Injection** tab. You will see all 12 Exxon fault
channels. Activate **Channel 5 — Cisco Circuit Flap (Houston Refinery)**:

1. Click **"Channel 5"** to expand it
2. Click **"Inject Fault"**
3. Watch the log stream — you will see `linkDown` events for
   `cisco-sw-houston-01 GigabitEthernet0/47` appearing

> **Presenter note:** This is what Exxon's NOC would see in Elastic
> instead of OpenNMS. The same SNMP trap — now correlated with the APM
> data showing api-gateway error rate climbing on the same timeline.

---

## Step 2 — Explore SNMP + CMDB Data in Kibana

Switch to the **Elastic Serverless** tab and navigate to **Discover**.

### 2a — Find the SNMP Trap Events

In the index pattern selector, choose **`logs-snmp.trap-exxon`** (or search
all logs with `logs*`). Filter for:

```
event.type : "linkDown"
```

You will see SNMP trap events for multiple Cisco switches across Houston,
Midland, and Corpus Christi sites. Each event contains:

| Field | Example Value |
|---|---|
| `device.hostname` | `cisco-sw-houston-01` |
| `device.ip` | `10.12.5.22` |
| `network.interface` | `GigabitEthernet0/47` |
| `network.site` | `Houston-Refinery-Campus` |
| `snmp.trap.type` | `linkDown` |

### 2b — See the CMDB Enrichment

Click any `linkDown` event and expand the document. Scroll to the CMDB fields:

| Field | Example Value |
|---|---|
| `cmdb.asset_tag` | `CHG0043891` |
| `cmdb.ci_class` | `Cisco Catalyst 9300` |
| `application.owner` | `exxon-infrastructure-2.0-team` |
| `business.service` | `Upstream-Operations` |
| `thousandeyes.agent_id` | `TE-HOU-001` |

> **This is the magic.** The SNMP trap came in with just an IP address.
> Elastic's enrich policy joined it with the ServiceNow CMDB at query time
> to show *which business service this switch supports* — no ETL, no JOIN
> query, no manual lookup.

---

## Step 3 — Cross-Correlate: Network + APM on the Same Timeline

In the **Elastic Serverless** tab, navigate to **Dashboards** → open the
**"Exxon Infrastructure 2.0 Executive Dashboard"**.

Find the **APM Errors Over Time** panel and the **Log Volume** panel. Notice
that SNMP `linkDown` events and `api-gateway` error spikes share the same
timestamp window.

> **This is the unified timeline Exxon can't build today.** OpenNMS shows
> the circuit flap. Datadog shows the API errors. Elastic shows both —
> with the CMDB enrichment proving which switch caused which service impact.

Navigate to **Alerts** → **Rules** and find the alert rule for
**"Channel 05: Cisco Circuit Flap — Houston Refinery"** — this rule would
page the WAN team and the app team simultaneously from one platform.

---

## Step 4 — Ask the AI Agent

Navigate to **AI Agent** (search "Agent Builder") and ask the
**exxon-infrastructure-analyst**:

> *"Show me the SNMP circuit flap events and which application services
> they are correlated with."*

> *"What Cisco switch is flapping at the Houston refinery and what business
> service does it support?"*

The agent uses ES|QL to join `logs-snmp.trap-exxon` with the CMDB data
and cross-references `api-gateway` error logs — the same query that would
take 45 minutes of manual cross-team investigation today.

---

## Why This Matters for Exxon

| Before (OpenNMS + Datadog) | After (Elastic Serverless) |
|---|---|
| SNMP traps in OpenNMS — invisible to app team | SNMP traps in same index as APM traces |
| Manual CMDB lookup to identify device owner | Enrich policy joins CMDB at query time |
| ThousandEyes data WAN-team-only | ThousandEyes `agent_id` correlated with SNMP and APM |
| Separate alert rules in 3 tools | One Elastic alert rule notifies all teams |

> Continue to Challenge 3 — the full end-user experience investigation.
