---
slug: unified-apm-logs
id: 5las0ca0droc
type: challenge
title: 'Challenge 1: Unifying Modern APM and Logs with OTel'
teaser: Replace fragmented Datadog/Splunk pipelines with native OpenTelemetry ingest
  into Elastic Serverless — bridging 1,000+ Azure API service instances and OpenShift
  Kubernetes in one query.
notes:
- type: text
  contents: |
    Exxon runs **1,000+ application instances** in Azure API Services, each
    emitting traces and metrics. Today these land in Datadog (traces) and
    Splunk (logs) — two tools with no common service identity.

    Log pipelines in Datadog are **failing to create**, and the OTel
    collector configurations that were meant to fix this are orphaned —
    "nobody knows what to do with OpenTelemetry."

    Elastic Serverless accepts **OTLP natively** — no APM Server to deploy,
    no Logstash pipeline to write. Elastic manages the collector backend for you.
- type: text
  contents: |
    **Elastic Serverless has a managed OTLP ingest endpoint.**

    Instead of standing up and operating an OTel Collector backend on your own
    infrastructure, Elastic Serverless provides a single HTTPS endpoint:

    ```
    https://<project>.ingest.<region>.aws.elastic.cloud:443
    ```

    Point your existing OTel SDKs, agents, or collectors here. Elastic routes
    signals automatically:

    - **Traces** → APM (service maps, latency, error rate)
    - **Metrics** → Metrics Explorer (host CPU, pod memory, custom gauges)
    - **Logs** → Logs Explorer (structured fields, full-text search)
- type: text
  contents: |
    **Exxon's orphaned OTel configs — fixed with one line change.**

    The collectors Exxon deployed (and then abandoned) already speak OTLP.
    The only configuration change needed:

    ```yaml
    exporters:
      otlphttp/elastic:
        # Before: Datadog Agent endpoint or nothing
        # After:  Elastic Serverless managed ingest endpoint
        endpoint: "https://<project>.ingest.<region>.aws.elastic.cloud:443"
        headers:
          Authorization: "ApiKey <your-api-key>"
    ```

    No Logstash. No Splunk HEC. No custom index templates.
    One endpoint, all three signal types.
- type: text
  contents: |
    **Why OTel + Elastic over vendor agents?**

    | | Datadog Agent | Splunk UF | OTel → Elastic Serverless |
    |---|---|---|---|
    | License cost | Per host | Per GB | Free (Apache 2.0) |
    | Vendor lock-in | High | High | None |
    | SNMP support | Add-on | No | Native |
    | Collector backend to operate | Yes | Yes | **No — Elastic manages it** |
    | Runs on OpenShift | Limited | Limited | Yes |

    Exxon's existing OTel configs — currently orphaned — can be pointed at
    Elastic Serverless with **a single endpoint URL change**.
- type: text
  contents: |
    **Elastic Serverless automatically detects OTel signal types.**

    All three signal types land in the same project under consistent
    field names. Correlate app logs, infra metrics, and APM spans for any
    Azure API service with one ES|QL query:

    ```sql
    FROM logs-*, metrics-*, traces-apm-*
    | WHERE service.name == "exxon-api-gateway"
    | STATS avg_latency = AVG(transaction.duration.us)
    ```

    One bill. One query language. Zero custom pipelines.
tabs:
- id: 5hcn3kt9phei
  title: Demo App
  type: service
  hostname: es3-api
  path: /
  port: 8090
- id: tpgjkiktcvye
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
difficulty: basic
timelimit: 1800
enhanced_loading: null
---

# Challenge 1: Unifying Modern APM and Logs with OTel

## The Situation

Your team manages **1,000+ Azure API Service instances** — the backbone of
Exxon's Infrastructure 2.0 microservices platform. Right now their telemetry
is split:

| Signal | Current Tool | Problem |
|--------|-------------|---------|
| Distributed traces | Datadog APM | Log pipeline creation is failing |
| Application logs | Splunk | No shared service identity with traces |
| Container metrics | Datadog Agent (OpenShift) | OTel config is orphaned — "nobody knows what to do" |

The goal: point Exxon's existing OTel instrumentation directly at the
**Elastic Serverless managed OTLP endpoint** — no collector backend to operate.

---

## Step 1 — Review the OTel Collector Architecture

Elastic Serverless provides a **managed OTLP ingest endpoint** — you do not
deploy or operate any collector backend on Elastic's side. Exxon's Azure API
services and OpenShift clusters send OTLP directly here.

The gateway collector running close to Exxon's infrastructure needs only this:

```yaml
exporters:
  otlphttp/elastic:
    # Elastic Serverless managed ingest endpoint
    # (.ingest. subdomain — NOT the .es. Elasticsearch endpoint)
    endpoint: "https://<project>.ingest.<region>.aws.elastic.cloud:443"
    headers:
      Authorization: "ApiKey <your-key>"

service:
  pipelines:
    traces/azure-api:
      receivers:  [otlp/azure-api]   # Azure API service SDK
      exporters:  [otlphttp/elastic]
    metrics/openshift:
      receivers:  [prometheus/openshift]  # OpenShift pod metrics
      exporters:  [otlphttp/elastic]
    logs/network:
      receivers:  [snmp]             # Cisco switch SNMP traps
      exporters:  [otlphttp/elastic]
```

> **Presenter note:** This is the pitch. Exxon's OTel collectors exist
> today. They're abandoned because nobody knew where to send the data.
> The answer is: **one HTTPS endpoint**. Elastic manages the rest.

---

## Step 2 — Confirm Deployment is Running

Switch to the **Demo App** tab. You will see:

- **Exxon Infrastructure 2.0** scenario selected (teal highlight)
- **"Connected! Cluster: ... | OTLP OK"** — both Elasticsearch and the managed
  OTLP ingest endpoint are verified
- **"Deploying..."** → then transitions to **"Launch"** when complete

> **Point out "OTLP OK"** — this confirms Elastic's managed OTLP endpoint
> is live and accepting data. No APM Server or collector backend needed.

Once deployment completes, scroll down in the Demo App to see the
**Deployment Progress** panel showing all 12 steps with green checkmarks.

---

## Step 3 — Explore What Landed in Elastic Serverless

Switch to the **Elastic Serverless** tab.

### 3a — Open the Exxon Executive Dashboard

Navigate to **Dashboards** (left nav) → look for **"Exxon Infrastructure 2.0
Executive Dashboard"**.

This dashboard was auto-created spanning all Exxon services — APM traces,
OpenShift metrics, and application logs in one view.

> **This is the "single pane of glass" Exxon asked for.** No custom
> Logstash pipeline. No per-team Datadog dashboard. One Elastic project,
> one dashboard, all signal types.

### 3b — Explore the AI Observability Agent

Navigate to **AI Agent** (search "Agent Builder" in the left nav). You will
see the **exxon-infrastructure-analyst** agent pre-configured with:

- Knowledge of all 12 Exxon fault channels
- ES|QL tools to query across APM traces, SNMP logs, and AVD metrics
- Remediation workflows tied to each fault type

Try asking:
> *"What fault channels are configured for Exxon's network infrastructure?"*

> *"Which services are affected by the Datadog log pipeline failure?"*

### 3c — Review Alert Rules

Navigate to **Alerts** → **Rules**. You will see **12 alert rules**
pre-created — one per Exxon fault channel — monitoring the appropriate
log streams with a shared KQL syntax.

> **In Datadog + Splunk, each rule lives in a different system with
> different syntax.** In Elastic Serverless, all 12 rules share one
> query engine, one alerting engine, one notification path.

### 3d — Navigate to Streams

Navigate to **Streams** (left nav under Observability). You will see the
**wired streams** that automatically parse and route OTLP signals:

- `logs` — application and SNMP logs
- `traces-apm-*` — distributed traces from Azure API services
- `metrics-*` — OpenShift pod and node metrics

Click any stream and try **"Query with ES|QL"** to see live data.

---

## Why This Matters for Exxon

| Before (Datadog + Splunk) | After (Elastic Serverless + OTel) |
|---|---|
| Separate APM and log searches across 2 UIs | One ES\|QL query across traces, metrics, and logs |
| Log pipeline creation failing in Datadog | No pipeline code — OTLP accepted natively |
| OTel configs orphaned — nobody owns the backend | One endpoint URL. Elastic manages the collector. |
| Datadog + Splunk storage bills | Single Elastic Serverless project, one bill |

> **"All the messages and logs per app in one dashboard"** — that's what
> just deployed. Continue to Challenge 2 to bring in the legacy network layer.
