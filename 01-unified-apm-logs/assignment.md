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

    Elastic Serverless accepts the **OpenTelemetry Line Protocol (OTLP)**
    natively over HTTP with zero pipeline code.
- type: text
  contents: |
    **Elastic Serverless OTLP Endpoint** accepts logs, metrics, and traces
    in a single ingest path — no Logstash pipelines, no custom index
    templates, no per-team Datadog dashboards to maintain.

    The `service.name` resource attribute from OTel becomes the unifying
    key across APM traces (`traces-apm-*`), infrastructure metrics
    (`metrics-*`), and application logs (`logs-*`).
- type: text
  contents: |
    **Did you know?** The same OTel Collector that routes SNMP traps from
    Cisco switches can also forward APM traces from Azure API Services.

    A single `receivers → processors → exporters` pipeline in your OTel
    Collector config handles both worlds:

    ```yaml
    receivers:
      snmp:            # ← legacy Cisco infrastructure
        endpoint: udp://0.0.0.0:162
      otlp:            # ← modern Azure API services
        protocols: { http: { endpoint: "0.0.0.0:4318" } }
    exporters:
      otlphttp:
        endpoint: ${ELASTIC_APM_SERVER_URL}
        headers:
          Authorization: "ApiKey ${ELASTICSEARCH_API_KEY}"
    ```

    One collector, one destination, zero extra pipelines.
- type: text
  contents: |
    **Why OTel over vendor agents?**

    | | Datadog Agent | Splunk UF | OTel Collector |
    |---|---|---|---|
    | License cost | Per host | Per GB | Free (Apache 2.0) |
    | Vendor lock-in | High | High | None |
    | SNMP support | Add-on | No | Native |
    | OTLP export | No | No | Native |
    | Runs on OpenShift | Limited | Limited | Yes |

    Exxon's existing OTel configs — currently orphaned — can be **pointed
    directly at Elastic Serverless** with a single endpoint change.
- type: text
  contents: |
    **Elastic Serverless automatically detects OTel signal types:**

    - **Traces** → APM UI (service maps, latency, error rate, Apdex)
    - **Metrics** → Metrics Explorer (host CPU, pod memory, custom gauges)
    - **Logs** → Logs Explorer (structured log fields, full-text search)

    All three land in the same project. An ES|QL query like:

    ```sql
    FROM logs-*, metrics-*, traces-apm-*
    | WHERE service.name == "exxon-api-gateway"
    | STATS avg_latency = AVG(transaction.duration.us)
    ```

    ...correlates app logs, infra metrics, and APM spans for any Azure
    API service — in milliseconds, across 1,000+ instances.
tabs:
- id: qje4n9p40moe
  title: Terminal
  type: terminal
  hostname: es3-api
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

The goal: point **one** OpenTelemetry collector at Elastic Serverless and
watch all three signal types land in a single, queryable platform.

---

## Step 1 — Explore the Mock Environment

A local **mock OTel collector** and **mock Elastic endpoint** have been
pre-configured in `/root/exxon-otel/`. Review the collector configuration:

```bash
cat /root/exxon-otel/otel-collector-config.yaml
```

Notice the three pipelines:
- `traces/azure-api` — simulated Datadog-style APM traces from Azure API services
- `metrics/openshift` — Prometheus scrape from simulated OpenShift pods
- `logs/splunk-forward` — Splunk-style forwarded application logs reformatted as OTLP

All three pipelines share one exporter: `otlphttp/elastic` pointing at the
local mock Elastic Serverless OTLP endpoint on `http://localhost:8200`.

---

## Step 2 — Start the Simulated Data Flow

Run the setup script to start the mock collector and begin sending data:

```bash
cd /root/exxon-otel
./generate-telemetry.sh
```

You will see output confirming three streams are active:

```
[INFO] Sending traces  → http://localhost:8200/...  (service: exxon-azure-api-gateway)
[INFO] Sending metrics → http://localhost:8200/...  (k8s.cluster.name: openshift-prod)
[INFO] Sending logs    → http://localhost:8200/...  (service: payment-processor-v2)
```

> **Presenter note:** This replaces the broken Datadog log pipeline. Same
> OTel collector config — different exporter URL. No Logstash. No Splunk HEC.

---

## Step 3 — Explore What Was Deployed to Elastic Serverless

Switch to the **Elastic Serverless** tab. The `generate-telemetry.sh`
script launched the Exxon scenario which deployed the following to your
Elastic Serverless project:

### 3a — Open the Exxon Executive Dashboard

In Kibana, navigate to **Dashboards** (left nav). Look for the
**"Exxon Infrastructure 2.0"** dashboard. This unified dashboard was
created automatically and spans all Exxon services.

> **Presenter note:** This is the "single pane of glass" Exxon has asked
> for. No custom Logstash pipeline. No per-team Datadog dashboard. One
> Elastic project, one dashboard, all data sources.

### 3b — Explore the AI Observability Agent

In Kibana, navigate to **AI Agent** (or search for "Agent Builder" in the
left nav). You will see the **exxon-infra2-analyst** agent pre-configured
with:

- Knowledge of all 12 Exxon fault channels (Datadog pipeline failures,
  Cisco circuit flapping, AppGate certificate expiry, Jitter DNS, etc.)
- ES|QL tools to query across APM traces, SNMP logs, and AVD metrics
- Remediation workflows for each fault type

Ask the agent:
> *"What fault channels are configured for Exxon's network infrastructure?"*

### 3c — Check Alert Rules

In Kibana, navigate to **Alerts** → **Rules**. You will see **12 alert
rules** pre-created — one per Exxon fault channel — each monitoring the
appropriate log streams for Exxon's error signatures.

> **Presenter note:** In Datadog + Splunk, each of these rules lives in a
> different system with different syntax. In Elastic Serverless, all 12
> rules share one query syntax (KQL), one alerting engine, and one
> notification path.

### 3d — Check the Knowledge Base

In the Terminal tab, query the Exxon knowledge base that was indexed:

```bash
ES_URL=$(agent variable get ES_URL)
API_KEY=$(agent variable get ES_API_KEY)
curl -sf -H "Authorization: ApiKey $API_KEY" \
  "$ES_URL/exxon-knowledge-base/_search?pretty&size=3&q=*" \
  | python3 -m json.tool | grep '"title"'
```

You should see 12 documents — one for each Exxon fault channel — ready
for the AI agent to query during a live incident.

---

## Step 5 — Validate: Find the Unified Service Tag

To complete this challenge, run the validation script:

```bash
/root/exxon-otel/check-unified-tags.sh
```

The script verifies the Exxon scenario is running and that the Elastic
deployment completed successfully.

A successful validation prints:

```
  ✓ Exxon scenario is active
  ✓ Challenge 1 complete — unified APM and logs with OTel
```

> **Tip:** You can also check deploy progress from the Terminal:
> ```bash
> curl -sf http://localhost:8090/api/setup/progress | python3 -m json.tool
> ```

---

## Why This Matters for Exxon

| Before (Datadog + Splunk) | After (Elastic Serverless + OTel) |
|---|---|
| Separate APM and log searches across 2 UIs | One ES|QL query across traces, metrics, and logs |
| Log pipeline creation failing in Datadog | No pipeline code — OTel OTLP accepted natively |
| OTel configs "orphaned" — nobody owns them | Standard OTel exporter URL — any collector works |
| No cost visibility across storage engines | Single Elastic Serverless project, one bill |

> **"All the messages and logs per app in one dashboard"** — this is that
> dashboard. Continue to Challenge 2 to bring in the legacy network layer.
