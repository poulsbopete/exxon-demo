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
- id: qiepitwglmmp
  title: Demo App
  type: service
  hostname: es3-api
  path: /
  port: 8090
- id: r3qjz8amhnjc
  title: Fault Injection
  type: service
  hostname: es3-api
  path: /chaos?deployment_id=exxon
  port: 8090
- id: xc2i7kyk4vty
  title: Elastic Serverless
  type: service
  hostname: es3-api
  path: /app/discover#/?_a=(query:(esql:'FROM logs*\n| WHERE snmp.trap.type IS NOT NULL\n| KEEP @timestamp,device.hostname,network.interface,snmp.trap.type\n| SORT @timestamp DESC\n| LIMIT 20'))
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

## Step 2 — Query SNMP + CMDB Data with ES|QL

Switch to the **Elastic Serverless** tab. Click the **ES|QL** button in the
top bar of Discover.

### 2a — Find the SNMP Trap Events

Paste this query and click **Run**:

```esql
FROM logs*
| WHERE snmp.trap.type IS NOT NULL
| KEEP @timestamp, device.hostname, network.interface, network.site, snmp.trap.type, message
| SORT @timestamp DESC
| LIMIT 20
```

You will see SNMP trap events for Cisco switches across Houston, Midland,
and Corpus Christi — `device.hostname`, `network.interface`, `network.site`,
and `snmp.trap.type` all in one table.

### 2b — Count Flaps by Switch (the NOC View)

```esql
FROM logs*
| WHERE snmp.trap.type == "linkDown"
| STATS flap_count = COUNT(*), interfaces = VALUES(network.interface)
    BY device.hostname, network.site
| SORT flap_count DESC
```

> **This query in OpenNMS requires a custom report. In Elastic: one line.**

### 2c — Cross-Correlate: Network Flap + APM Errors on the Same Timeline

Now join the SNMP events with application error logs in a single query:

```esql
FROM logs*
| WHERE (snmp.trap.type == "linkDown") OR (service.name == "api-gateway" AND log.level == "ERROR")
| KEEP @timestamp, snmp.trap.type, device.hostname, service.name, message
| SORT @timestamp DESC
| LIMIT 30
```

You will see `linkDown` traps from `cisco-sw-houston-01` and `api-gateway`
ERROR logs interleaved on the **same timeline** — the circuit flap causing
the API errors, visible in one query.

> **This is what Exxon can't do today.** OpenNMS shows the circuit flap.
> Datadog shows the API errors. Elastic shows both — in a single ES|QL query.

---

## Step 3 — Alert Rule

Navigate to **Alerts** → **Rules** and find the alert rule for
**"Channel 05: Cisco Circuit Flap — Houston Refinery"** — this rule pages
the WAN team and the app team simultaneously from one platform.

---

## Step 4 — Ask the AI Agent

In the **left navigation**, click **AI Agent** (not the chat bubble icon in the top bar — that is the legacy AI Assistant). Ask the
**exxon-infrastructure-analyst**:

> *"Show me the SNMP circuit flap events and which application services
> they are correlated with."*

> *"What Cisco switch is flapping at the Houston refinery and what business
> service does it support?"*

The agent uses ES|QL to query `logs*` for SNMP trap events and
cross-references `api-gateway` error logs — the same correlation that
takes 45 minutes of manual cross-team investigation today.

---

## Why This Matters for Exxon

| Before (OpenNMS + Datadog) | After (Elastic Serverless) |
|---|---|
| SNMP traps in OpenNMS — invisible to app team | SNMP traps in same index as APM traces |
| Manual CMDB lookup to identify device owner | Enrich policy joins CMDB at query time |
| ThousandEyes data WAN-team-only | ThousandEyes `agent_id` correlated with SNMP and APM |
| Separate alert rules in 3 tools | One Elastic alert rule notifies all teams |

> Continue to Challenge 3 — the full end-user experience investigation.
