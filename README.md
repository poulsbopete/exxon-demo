# Elastic Serverless for Exxon — Instruqt Demo Track

**Track slug:** `elastic-exxon-serverless-observability`  
**Target audience:** Exxon Infrastructure 2.0 engineering team, Elastic pre-sales SEs  
**Duration:** ~45–60 minutes (3 challenges × 15–20 min each)  
**Sandbox:** Lightweight Linux container (no Kubernetes required)

---

## Overview

This Instruqt track is purpose-built to address Exxon's fragmented observability
environment and make the case for **Elastic Serverless** as their unified platform.

| Current Exxon Tool | Pain Point | Replaced by |
|---|---|---|
| Datadog (APM + metrics) | Log pipelines failing to create | Elastic Serverless OTLP endpoint |
| Splunk (app logs) | No shared identity with Datadog traces | OTLP logs → `logs-apm-*` |
| OpenNMS (SNMP) | Isolated from application data | Elastic SNMP integration |
| ThousandEyes (Cisco) | WAN team only, no app correlation | ThousandEyes integration + CMDB enrich |
| Manual EUX investigation | 45–90 min cross-team Slack threads | Unified Kibana dashboard + ES|QL |

---

## Track Structure

```
exxon-demo/
├── track.yml                          # Instruqt track definition
├── README.md                          # This file
│
├── 01-unified-apm-logs/
│   ├── assignment.md                  # Challenge 1 instructions
│   ├── setup-sandbox.sh               # Environment setup (auto-run by Instruqt)
│   └── check-sandbox.sh               # Validation (auto-run on "Check")
│
├── 02-legacy-snmp-network/
│   ├── assignment.md                  # Challenge 2 instructions
│   ├── setup-sandbox.sh
│   └── check-sandbox.sh
│
└── 03-single-pane-eux/
    ├── assignment.md                  # Challenge 3 instructions
    ├── setup-sandbox.sh
    └── check-sandbox.sh
```

---

## Challenge Summary

### Challenge 1: Unifying Modern APM and Logs with OTel (~15 min)

**Narrative:** Exxon's 1,000+ Azure API service instances emit traces into
Datadog and logs into Splunk — two tools with no common service identity.
OTel configs are "orphaned — nobody knows what to do."

**What happens in the sandbox:**
- A mock Elastic OTLP endpoint starts on `localhost:8200`
- A telemetry generator sends OTel traces, metrics, and logs for three
  simulated Azure API services (`exxon-azure-api-gateway`, `payment-processor-v2`,
  `inventory-service-v3`) and OpenShift Kubernetes pod metrics
- The user runs the generator and validates that `service.name` bridges
  traces, metrics, and logs in a single ES|QL query

**Key Elastic capability demonstrated:**  
Native OTLP ingest — no Logstash, no pipeline code, no Splunk HEC.

**Validation:** `check-unified-tags.sh` verifies all three signal types share
a common `service.name` resource attribute.

---

### Challenge 2: Taming Legacy Network Infrastructure (SNMP) (~20 min)

**Narrative:** Cisco WAN switches emit SNMP v2c traps into OpenNMS — invisible
to application teams. ThousandEyes agents on the same switches provide
circuit-level data, but only the WAN team can see it.

**What happens in the sandbox:**
- CMDB device records and SNMP trap data are posted directly to Elastic Serverless
- 12 ServiceNow CMDB device records are loaded (hostname → site → app owner
  → ThousandEyes agent ID)
- A trap generator sends simulated Cisco `linkDown`/`linkUp` events with
  circuit flapping on `cisco-sw-houston-01`
- ES|QL queries correlate SNMP events to CMDB enrichment data

**Key Elastic capability demonstrated:**  
Elastic SNMP integration + runtime field enrichment joins CMDB data to
SNMP traps at query time — no ETL.

**Validation:** `check-snmp-ingest.sh` verifies CMDB loaded, traps ingested,
`network.site` populated from CMDB, and ≥ 2 sites affected by `linkDown`.

---

### Challenge 3: Single Pane of Glass for End-User Experience (~20 min)

**Narrative:** A Midland field engineer (`jsmith`) reports that their Azure
Virtual Desktop session is unusable. Is it AWS fallback latency? Jitter DNS
from the WAN team? Or an AppGate Zero Trust policy block?

**What happens in the sandbox:**
- Five simulated datasets are pre-generated:
  - AVD session reliability metrics (elevated reconnects, slow logon)
  - Windows Security event logs (multiple Event ID 4625 login failures)
  - iboss connection log (`audit.exxon.internal` repeatedly blocked)
  - AppGate Zero Trust audit (`Audit-System-Access` entitlement denied —
    expired device certificate)
  - ThousandEyes circuit metrics (elevated jitter on Midland-MPLS-to-Azure)
- A unified HTML dashboard serves on `localhost:5601/dashboard`
- The user runs `investigate.py` to correlate all five data streams
- Root cause: **APPGATE_POLICY** (expired device cert → iboss blocks +
  AppGate denials, with JITTER_DNS as a contributing factor)

**Key Elastic capability demonstrated:**  
`user.name` and `host.name` as universal join keys across AVD, Windows,
iboss, AppGate, and ThousandEyes — answering "How is the machine functioning
for the user?" in minutes.

**Validation:** `check-eux-investigation.sh` verifies all five data files
exist and that `investigate.py` produces a non-UNKNOWN root cause.

---

## SE Presenter Talk Track

### Opening (before Challenge 1)

> "Exxon, you've described your environment as 'very disjointed.' You have
> Datadog for APM, Splunk for application logs, OpenNMS for SNMP network
> events, and ThousandEyes on your Cisco switches — four tools, four teams,
> four bills, and log pipelines in Datadog that are failing to create.
>
> What I'm going to show you today is what your Infrastructure 2.0 world
> looks like when all of that lands in a single Elastic Serverless project.
> No Logstash. No Splunk HEC. No per-team APM dashboards. One platform,
> one query language, one retention policy."

### After Challenge 1

> "That ES|QL query just joined APM traces from your Azure API services
> with container metrics from OpenShift — using the same `service.name`
> tag the OTel collector already sets. This is the view your app team
> has never had. And notice: we didn't write a single Logstash pipeline.
> We changed one URL in the OTel collector config."

### After Challenge 2

> "Your WAN team already sees link-down events in OpenNMS. What's new here
> is that the app team sees them too — in the same Kibana instance where
> they watch their APM traces. The ES|QL query joined the SNMP trap to
> the ServiceNow CMDB data in milliseconds. No ETL. No scheduled jobs.
> And because we stored the ThousandEyes agent ID in the CMDB record,
> you can correlate circuit-level packet loss to the SNMP link-down in
> the same query."

### After Challenge 3

> "Forty-five minutes of cross-team Slack. That's what this investigation
> takes today. The WAN team is looking at ThousandEyes. The security team
> is looking at AppGate. The desktop team is looking at Windows event logs.
> Nobody has `jsmith`'s full picture.
>
> Here, `user.name` is the join key. One query, five data streams, five
> minutes. The answer: expired device certificate, caught by both iboss
> and AppGate. The WAN jitter is a contributing factor — probably masking
> the auth retry storm — but the root cause is the cert. Your desktop team
> can re-enroll in Intune right now.
>
> And this isn't a custom integration we built for you. This is the Elastic
> Agent with the iboss integration, the AppGate integration, the Windows
> integration, and the ThousandEyes integration — all pointing at the same
> Elastic Serverless project."

---

## Deploying to Instruqt

```bash
# Install Instruqt CLI
brew install instruqt/tap/instruqt

# Authenticate
instruqt auth login

# Validate the track
instruqt track validate --dir /Users/psimkins/opt/exxon-demo

# Push to Instruqt
instruqt track push --dir /Users/psimkins/opt/exxon-demo

# Create a sandbox for testing
instruqt track create-invite --track elastic-exxon-serverless-observability --title "Exxon Demo"
```

---

## Environment Variables (set in Instruqt sandbox config)

| Variable | Value | Notes |
|---|---|---|
| `ES_URL` | Elastic Serverless ES endpoint | Set by track provisioning via `agent variable set` |
| `ES_KIBANA_URL` | Elastic Serverless Kibana endpoint | Set by track provisioning |
| `ES_API_KEY` | API key (base64 encoded) | Set by track provisioning |
| `DEMO_USER` | `jsmith` | EUX investigation target user |
| `DEMO_SITE` | `Midland-Field-Ops` | EUX investigation target site |

---

## Files Reference

| File | Purpose |
|---|---|
| `track.yml` | Instruqt track definition (challenges, tabs, timing) |
| `01-unified-apm-logs/assignment.md` | Challenge 1 instructions |
| `01-unified-apm-logs/setup-sandbox.sh` | Starts mock OTLP endpoint, writes OTel config and telemetry generator |
| `01-unified-apm-logs/check-sandbox.sh` | Validates unified `service.name` tag across traces/metrics/logs |
| `02-legacy-snmp-network/assignment.md` | Challenge 2 instructions |
| `02-legacy-snmp-network/setup-sandbox.sh` | Starts mock Elasticsearch, writes SNMP config, CMDB loader, trap sender |
| `02-legacy-snmp-network/check-sandbox.sh` | Validates CMDB loaded, traps ingested, multi-site enrichment |
| `03-single-pane-eux/assignment.md` | Challenge 3 instructions |
| `03-single-pane-eux/setup-sandbox.sh` | Generates all five EUX datasets, starts dashboard server |
| `03-single-pane-eux/check-sandbox.sh` | Validates datasets exist and root cause is identified |
