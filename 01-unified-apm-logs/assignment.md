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

The goal: point Exxon's existing OTel instrumentation directly at the
**Elastic Serverless managed OTLP endpoint** and watch all three signal
types land in one platform — no collector infrastructure to operate.

---

## Step 1 — Review the Collector Config

Elastic Serverless provides a **managed OTLP ingest endpoint** — you do not
deploy or operate any collector backend on Elastic's side. Exxon's Azure API
services and OpenShift clusters send OTLP directly here.

Review the collector config that would run **close to Exxon's infrastructure**
(e.g., as a DaemonSet on OpenShift):

```bash
cat /root/exxon-otel/otel-collector-config.yaml
```

Notice the exporter section — the **only Elastic-specific configuration** is
one endpoint URL and one API key header:

```yaml
exporters:
  otlphttp/elastic:
    endpoint: "https://<project>.ingest.<region>.aws.elastic.cloud:443"
    headers:
      Authorization: "ApiKey <your-key>"
```

Everything else (receivers, processors, pipelines) is standard OTel.
Exxon's orphaned collector configs already have this structure — they just
need the endpoint URL updated.

> **Presenter note:** This is the pitch. Exxon's OTel collectors exist
> today. They're abandoned because nobody knew where to send the data.
> The answer is: one HTTPS endpoint. Elastic manages the rest.

---

## Step 2 — Activate the Telemetry Flow

The demo app sends OTLP traces, metrics, and logs directly to your Elastic
Serverless project. Start the flow:

```bash
cd /root/exxon-otel
./generate-telemetry.sh
```

You will see output confirming all three streams are active and going to
**Elastic Serverless** — not a local process, not a mock endpoint:

```
[telemetry] Exxon scenario already active ✓
[telemetry] Telemetry streams now active:
[telemetry]   [INFO] Sending traces  → Elastic APM  (service: exxon-azure-api-gateway)
[telemetry]   [INFO] Sending traces  → Elastic APM  (service: payment-processor-v2)
[telemetry]   [INFO] Sending metrics → Elastic Metrics (k8s.cluster.name: openshift-prod)
[telemetry]   [INFO] Sending logs    → Elastic Logs   (service: inventory-service-v3)
```

> **Presenter note:** This replaces the broken Datadog log pipeline and
> the disconnected Splunk forwarder. Same OTel instrumentation — new
> destination. No Logstash. No Splunk HEC. No custom index templates.

---

## Step 3 — Explore What Landed in Elastic Serverless

Switch to the **Elastic Serverless** tab. The scenario deployed the following
assets to your project automatically:

### 3a — Open the Exxon Executive Dashboard

Navigate to **Dashboards** (left nav) → **"Exxon Infrastructure 2.0"**.

This unified dashboard was auto-created and spans all Exxon services — APM
traces, OpenShift metrics, and application logs in one view.

> **Presenter note:** This is the "single pane of glass" Exxon asked for.
> No custom Logstash pipeline. No per-team Datadog dashboard. One Elastic
> project. One dashboard. All signal types.

### 3b — Explore the AI Observability Agent

Navigate to **AI Agent** (or search "Agent Builder" in the left nav). You
will see the **exxon-infra2-analyst** agent pre-configured with:

- Knowledge of all 12 Exxon fault channels (Datadog pipeline failures,
  Cisco circuit flapping, AppGate certificate expiry, Jitter DNS, etc.)
- ES|QL tools to query across APM traces, SNMP logs, and AVD metrics
- Remediation workflows for each fault type

Ask the agent:
> *"What fault channels are configured for Exxon's network infrastructure?"*

### 3c — Check Alert Rules

Navigate to **Alerts** → **Rules**. You will see **12 alert rules**
pre-created — one per Exxon fault channel — each monitoring the appropriate
log streams for Exxon's error signatures.

> **Presenter note:** In Datadog + Splunk, each of these rules lives in a
> different system with different syntax. In Elastic Serverless, all 12
> rules share one query syntax (KQL), one alerting engine, one notification
> path.

### 3d — Query the Knowledge Base

In the Terminal tab, confirm the Exxon knowledge base was indexed:

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

## Step 4 — Validate: Confirm the Deployment

Run the validation script to confirm the scenario is active and the Elastic
deployment completed:

```bash
/root/exxon-otel/check-unified-tags.sh
```

A successful run prints:

```
  ✓ Exxon scenario is active
  ✓ Challenge 1 complete — unified APM and logs with OTel
```

> **Tip:** Check deployment progress at any time:
> ```bash
> curl -sf http://localhost:8090/api/setup/progress | python3 -m json.tool
> ```

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
