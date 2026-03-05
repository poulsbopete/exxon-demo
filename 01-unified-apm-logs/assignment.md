---
slug: unified-apm-logs
id: 5las0ca0droc
type: challenge
title: 'Challenge 1: Unifying Modern APM and Logs with OTel'
teaser: Replace fragmented Datadog/Splunk pipelines with native OpenTelemetry ingest
  into Elastic Serverless — bridging 1,000 Azure API service instances and OpenShift
  Kubernetes in one query.
notes:
- type: text
  contents: |
    Exxon runs **1,000 application instances** in Azure API Services, each
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

Your team manages **1,000 Azure API Service instances** — the backbone of
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

## Step 3 — Query Unified APM Traces in ES|QL

Once data is flowing, open the ES|QL console and run the following query
to see all services reporting traces in the last 15 minutes:

```esql
FROM traces-apm-* METADATA _index
| WHERE @timestamp > NOW() - 15 minutes
| STATS
    total_transactions = COUNT(*),
    p95_latency_ms     = PERCENTILE(transaction.duration.us, 95) / 1000,
    error_rate_pct     = ROUND(
                           100.0 * COUNT_IF(event.outcome == "failure") / COUNT(*),
                           2
                         )
  BY service.name
| SORT error_rate_pct DESC
| LIMIT 20
```

You should see `exxon-azure-api-gateway`, `payment-processor-v2`, and
`inventory-service-v3` — the three simulated Azure API services — alongside
their p95 latency and error rates.

> **This is the view Exxon's app teams have never had.** Previously, error
> rates lived in Datadog; latency percentiles were only visible to whoever
> had a Datadog APM seat license.

---

## Step 4 — Bridge Traces and Container Metrics

Now run the **unified join query** — bridging APM service data with
OpenShift container metrics using `service.name` as the common key:

```bash
cat /root/exxon-otel/queries/unified-service-query.esql
```

Run that query in the ES|QL console. It joins:
- `traces-apm-*` (error rates, latency from Azure API services)
- `metrics-kubernetes.*` (CPU/memory from OpenShift pods)

On a single service key: `service.name`.

**Expected output columns:**

| service.name | p95_latency_ms | error_rate_pct | pod_cpu_pct | pod_memory_mb |
|---|---|---|---|---|
| payment-processor-v2 | 342 | 4.2 | 87.3 | 1840 |
| inventory-service-v3 | 118 | 0.8 | 22.1 | 512 |
| exxon-azure-api-gateway | 89 | 0.3 | 31.4 | 768 |

Notice `payment-processor-v2`: high latency **and** high CPU on its
OpenShift pod. This correlation — impossible in Datadog+Splunk — is
available instantly here.

---

## Step 5 — Validate: Find the Unified Service Tag

To complete this challenge, run the validation script:

```bash
/root/exxon-otel/check-unified-tags.sh
```

The script queries the mock Elastic endpoint and verifies that:
1. All three index patterns (`traces-apm-*`, `metrics-kubernetes.*`, `logs-apm-*`) contain data
2. At least one document in each index shares a common `service.name` value
3. The `service.name` field is present as a resource attribute (OTel semantic convention)

A successful validation prints:

```
✓ traces-apm-*           → 3 services found
✓ metrics-kubernetes.*   → 3 services found
✓ logs-apm-*             → 3 services found
✓ Unified tag: service.name bridges all three signal types
✓ Challenge 1 complete — unified APM and logs with OTel
```

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
