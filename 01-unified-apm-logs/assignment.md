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

## Step 3 — Query Unified APM Traces in ES|QL

Switch to the **Elastic Serverless** tab. In Kibana, go to
**Discover → Change to ES|QL mode** (or **Dev Tools → Console**, then
switch to ES|QL).

> **Wait 60–90 seconds** after running `generate-telemetry.sh` for the
> first documents to arrive. If you get "Unknown column" errors, the
> index doesn't have data yet — try the warm-up query below first.

**Warm-up — confirm data is arriving:**

```esql
FROM logs-*,metrics-*,traces-*
| LIMIT 5
```

If that returns rows, APM data is flowing. Then run the full query:

```esql
FROM traces-apm-*
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

You should see `api-gateway`, `payment-processor`, and `inventory-service`
alongside their p95 latency and error rates.

> **This is the view Exxon's app teams have never had.** Previously, error
> rates lived in Datadog; latency percentiles were only visible to whoever
> had a Datadog APM seat license.

---

## Step 4 — Navigate to APM in the Elastic Serverless Tab

In the **Elastic Serverless** tab, click **APM** in the left nav. You will
see the Exxon services populating the service inventory. Click
**Service Map** to see the topology of:

- `api-gateway` → `payment-processor` → `inventory-service`
- All three reporting traces, latency, and error rate in one view

This replaces **three separate Datadog APM dashboards** — one per service
team — with a single correlated service map.

**Also check:** go to **Discover** and set the index pattern to
`logs-*` to see application logs flowing from the same services, tagged
with the same `service.name` — no Splunk required.

---

## Step 5 — Validate: Find the Unified Service Tag

To complete this challenge, run the validation script:

```bash
/root/exxon-otel/check-unified-tags.sh
```

The script verifies the Exxon scenario is running and queries Elastic to
confirm telemetry is arriving. Data can take **1–3 minutes** to appear
after `generate-telemetry.sh` runs — if checks fail, wait and retry.

A successful validation prints:

```
  ✓ Exxon scenario is active
  ✓ traces-apm-*           → N documents
  ✓ metrics-kubernetes.*   → N documents
  ✓ logs-apm-*             → N documents
  ✓ Challenge 1 complete — unified APM and logs with OTel
```

> **If you see "0 documents":** Data is still in transit. Wait 60 seconds
> and run `check-unified-tags.sh` again. The scenario sends data
> continuously so it will arrive.

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
