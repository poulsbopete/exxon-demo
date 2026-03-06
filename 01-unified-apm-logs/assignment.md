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

    Instead of standing up and operating an OTel Collector backend, Elastic
    Serverless provides a single HTTPS endpoint:

    ```
    https://<project>.ingest.<region>.aws.elastic.cloud:443
    ```

    Point your existing OTel SDKs, agents, or collectors here. Elastic routes
    signals automatically — traces, metrics, and logs in one stream.
- type: text
  contents: |
    **Exxon's orphaned OTel configs — fixed with one line change.**

    ```yaml
    exporters:
      otlphttp/elastic:
        endpoint: "https://<project>.ingest.<region>.aws.elastic.cloud:443"
        headers:
          Authorization: "ApiKey <your-api-key>"
    ```

    No Logstash. No Splunk HEC. No custom index templates.
    One endpoint. All three signal types. Zero pipeline code.
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

## Step 1 — Open the Demo App

Switch to the **Demo App** tab. The **Exxon Infrastructure 2.0** scenario is
already selected and the connection test runs automatically.

Scroll down to the **Connection Settings** panel and look for the green
status bar:

> **"Connected! Cluster: ... | OTLP OK"**

If the status hasn't appeared yet, click the **Test Connection** button once.

**"OTLP OK"** is the key message. It confirms that Elastic Serverless's
managed OTLP ingest endpoint is live and accepting telemetry — no APM Server
to deploy, no OTel Collector backend to configure on Elastic's side.

Exxon's orphaned OTel collectors just need their `endpoint:` URL updated.
That's it.

---

## Step 2 — Watch the Deployment Progress

Scroll down in the Demo App to the **Deployment Progress** panel. You will see
all 12 steps completing in real time:

| Step | What it does |
|---|---|
| Connectivity check | Confirms ES + Kibana are reachable |
| Derive OTLP endpoint | Finds the `.ingest.` URL — the managed OTel backend |
| Configure platform settings | Enables Wired Streams, Significant Events, AI Agent |
| Deploy workflows | Creates 4 automated remediation workflows |
| Index knowledge base | Loads 12 Exxon fault channel documents for the AI |
| Deploy AI agent tools | Configures 9 ES\|QL tools for the AI analyst |
| Create AI agent | Deploys the `exxon-infrastructure-analyst` AI agent |
| Create data views | Sets up `logs*`, `traces-*`, `metrics-*` data views |
| Import executive dashboard | Deploys the unified Exxon dashboard to Kibana |
| Create alert rules | Creates 12 alert rules — one per fault channel |

> **Presenter note:** Everything in this list is deployed programmatically
> in minutes. In Datadog + Splunk, each row is a separate team's
> multi-week project.

---

## Step 3 — Explore Elastic Serverless

Once the Deployment Progress panel shows all green checkmarks, switch to the
**Elastic Serverless** tab.

### Dashboard

Navigate to **Dashboards** → **"Exxon Infrastructure 2.0 Executive Dashboard"**.

This unified dashboard spans APM traces from Azure API services, metrics from
OpenShift pods, and application logs — all in one view, auto-created by the
Demo App.

> **"All the messages and logs per app in one dashboard"** — this is it.

### AI Agent

Click **AI Agent** in the top-right corner of Kibana to open the agent panel. Select **exxon-infrastructure-analyst**.

Ask:

```
What fault channels are configured for Exxon's network infrastructure?
```

```
Which Azure API services have the highest error rates?
```

### Alert Rules

Navigate to **Alerts** → **Rules**. You will see **12 alert rules**
pre-created — one per Exxon fault channel — all using KQL, all in one
alerting engine.

> In Datadog + Splunk, these 12 rules live in different systems with
> different syntax. Here: one platform, one notification path.

### Streams

Navigate to **Streams** (under Observability in the left nav). You will see
the Wired Streams automatically routing OTLP signals — look for:

- `logs.otel` — application logs from Azure API services
- `traces-generic.otel-default` — distributed traces from Azure API services
- `metrics-generic.otel-default` — host and service metrics
- `metrics-kubernetes.container.otel-default` — OpenShift pod and container metrics

> These stream names are auto-created by Elastic Serverless when your
> OTLP data lands. No pipeline code, no index templates — Elastic routes
> each signal type automatically.

Click any stream → **"Query with ES|QL"** to explore live telemetry.

---

## Why This Matters for Exxon

| Before (Datadog + Splunk) | After (Elastic Serverless + OTel) |
|---|---|
| Separate APM and log searches across 2 UIs | One ES\|QL query across traces, metrics, and logs |
| Log pipeline creation failing in Datadog | No pipeline code — OTLP accepted natively |
| OTel configs orphaned — nobody owns the backend | One endpoint URL. Elastic manages the collector. |
| Datadog + Splunk storage bills | Single Elastic Serverless project, one bill |

> Continue to **Challenge 2** to bring in the legacy Cisco SNMP network layer.
