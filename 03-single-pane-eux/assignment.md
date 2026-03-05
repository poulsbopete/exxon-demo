---
slug: single-pane-eux
id: pwr2sckdx9nb
type: challenge
title: 'Challenge 3: The Single Pane of Glass for End-User Experience'
teaser: Answer Exxon's critical question — "How is the machine functioning for the
  user?" — by investigating an Azure Virtual Desktop issue spanning iboss connections,
  AppGate Zero Trust, and Windows event logs in one unified Elastic dashboard.
notes:
- type: text
  contents: |
    Exxon manages **hundreds of Azure Virtual Desktop (AVD) sessions** for
    field engineers. Desktop reliability is measured by three teams in three
    tools — ThousandEyes (WAN), AppGate / iboss (Security), Windows Event
    Logs (Desktop). When a user reports "my desktop is slow," nobody has a
    single view.

    The question "Is this AWS fallback latency, Jitter DNS from the WAN
    team, or an AppGate policy block?" takes hours of cross-team Slack
    threads to answer.
- type: text
  contents: |
    **`user.name`** and **`host.name`** serve as universal join keys across
    AVD metrics, Windows events, iboss connection logs, AppGate audit logs,
    and ThousandEyes circuit data — no custom joins required. One ES|QL
    query, five data streams, five minutes to root cause.
- type: text
  contents: |
    **How Elastic ingests the EUX data stack:**

    | Source | Integration | Data Stream |
    |---|---|---|
    | Azure Virtual Desktop | Azure Monitor integration | `metrics-azure.compute-*` |
    | Windows Event Log | Elastic Agent (WinLog) | `logs-windows.forwarded-*` |
    | iboss Web Gateway | iboss integration / syslog | `logs-iboss.gateway-*` |
    | AppGate SDP | CEF syslog via Logstash | `logs-appgate.audit-*` |
    | ThousandEyes | ThousandEyes integration | `metrics-thousandeyes.*` |
    | Cisco SNMP (WAN) | OTel snmpreceiver | `logs-snmp.trap-*` |

    All six land in one Elastic Serverless project. The unified dashboard
    queries all six simultaneously using a single time filter.
- type: text
  contents: |
    **The power of OTel for SNMP in the EUX story:**

    ThousandEyes agents run *on Cisco switches*. When Jitter DNS causes
    a circuit flap, a chain of events fires within milliseconds:

    1. **SNMP trap** (`linkDown`) → OTel Collector → `logs-snmp.trap-*`
    2. **ThousandEyes** packet loss spike → `metrics-thousandeyes.*`
    3. **AppGate** device loses connectivity → `logs-appgate.audit-*`
    4. **AVD session** latency exceeds threshold → `metrics-azure.compute-*`
    5. **User** calls the help desk

    Elastic's timeline view shows all five events with a **shared
    timestamp correlation** — the root cause (step 1) is identified
    before the help desk ticket is even opened.
- type: text
  contents: |
    **"How is the machine functioning for the user?"**

    This is Exxon's core question. Today the answer requires:
    - Opening ThousandEyes (WAN team login)
    - Opening AppGate admin console (Security team login)
    - Opening Azure Portal (Cloud team login)
    - Waiting for cross-team Slack threads

    With Elastic Serverless, the answer is a **single dashboard** with
    one time range, one user filter, and one root-cause annotation —
    accessible to every team, from the NOC to the CISO, without
    extra tool licenses or per-seat costs.
tabs:
- id: 2rwz8loyldqp
  title: Demo App
  type: service
  hostname: es3-api
  path: /
  port: 8090
- id: 1z4wudkzrort
  title: Fault Injection
  type: service
  hostname: es3-api
  path: /chaos?deployment_id=exxon
  port: 8090
- id: ftzxguvojzh3
  title: Elastic Serverless
  type: service
  hostname: es3-api
  path: /app/observability/overview
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
timelimit: 2700
enhanced_loading: null
---

# Challenge 3: The Single Pane of Glass for End-User Experience

## The Situation

A field engineer in Midland contacts IT support: **"My Azure Virtual Desktop
session is unusable — applications are hanging and I can't connect to the
internal audit system."**

Three teams immediately get pinged on separate Slack channels:

| Team | Tool | Their View |
|---|---|---|
| WAN Team | ThousandEyes | Circuit jitter from Midland MPLS to Azure |
| Security Team | AppGate Zero Trust / iboss | Connection attempts to audit system |
| Desktop Team | Windows Event Logs | AVD session health, profile load times |

Without Elastic, it takes **45–90 minutes** of cross-team Slack threads to
determine: Is this AWS fallback latency? Jitter DNS from the WAN team?
An AppGate Zero Trust policy block?

With Elastic Serverless, the answer is in the Demo App fault channels and
the AI Agent — in under 5 minutes.

---

## Step 1 — Inject the EUX Fault Scenario

Switch to the **Fault Injection** tab and activate the compounding EUX
fault scenario. Inject these channels in sequence:

1. **Channel 6 — Midland MPLS Circuit Degradation**
   - ThousandEyes agent TE-MID-001 detects jitter > 45ms

2. **Channel 9 — AppGate Device Certificate Expired**
   - AppGate denies `Audit-System-Access` for `jsmith@exxon.com`
   - iboss blocks `audit.exxon.internal` simultaneously

3. **Channel 10 — Azure Virtual Desktop Session Storm**
   - 14 Midland field engineers report AVD sessions disconnecting
   - Logon times exceed 30 seconds (normal: < 5s)

4. **Channel 11 — Windows Event ID 4625 Storm (Jitter DNS Auth Failure)**
   - MPLS jitter causes Azure AD timeouts → account lockouts

Watch the fault log stream in the Demo App for all four signal types
appearing simultaneously — **this is what Exxon's NOC would see in
Elastic in real time, today they need 4 separate tool logins.**

---

## Step 2 — Open the Unified Dashboard

Switch to the **Elastic Serverless** tab. Navigate to **Dashboards** →
**"Exxon Infrastructure 2.0 Executive Dashboard"**.

Look at the timeline and identify the spike window. The dashboard shows:

- **APM errors** — `avd-broker` and `azure-ad-proxy` error rates climbing
- **Log volume** — application log spike matching the fault injection time
- **Significant events** — the fault channels appear as annotated events
  on the timeline

> **This is the "single pane of glass."** The WAN team's ThousandEyes
> data, the Security team's AppGate audit, and the Desktop team's AVD
> session metrics are all on the same time axis.

---

## Step 3 — Ask the AI Agent

In the **left navigation**, click **AI Agent** (not the chat bubble icon in the top bar — that is the legacy AI Assistant). Open the
**exxon-infrastructure-analyst** agent.

Ask the following questions to walk through the root cause investigation:

**Question 1 — Start with the user:**
> *"What is happening with user jsmith@exxon.com on host avd-mid-w10-042?"*

**Question 2 — Check the network:**
> *"Is there circuit jitter on the Midland MPLS path and is it causing
> authentication failures?"*

**Question 3 — Check Zero Trust:**
> *"Is AppGate denying access to audit.exxon.internal for Midland users?
> What is the deny reason?"*

**Question 4 — Identify root cause:**
> *"Is the Midland AVD issue caused by AWS fallback latency, Jitter DNS,
> or an AppGate policy block? What is the remediation?"*

The agent correlates across SNMP traps, ThousandEyes circuit metrics,
AppGate audit logs, Windows Event IDs, and AVD session data using
`user.name` and `network.site` as join keys — in seconds.

---

## Step 4 — The Root Cause

Based on the fault channels and AI Agent investigation, the root cause chain is:

```
Midland MPLS jitter > 45ms (ThousandEyes TE-MID-001)
    │
    ├─► DNS RTT jitter → Azure AD LDAP bind timeout (5000ms)
    │        → Windows Event ID 4625 (auth failure storm)
    │        → Account lockout (Event ID 4740) for jsmith
    │
    ├─► AppGate device cert expired (avd-mid-w10-042)
    │        → Audit-System-Access entitlement denied
    │        → iboss blocks audit.exxon.internal
    │
    └─► AVD session storm: 14 users, 47 reconnects in 90s
             → FSLogix profile mount timeout
             → Logon duration 38s (SLO: 5s)
```

**Root cause: JITTER_DNS** (Midland MPLS WAN) compounded by
**APPGATE_POLICY** (expired device certificate)

> **Presenter note:** In the current state, this investigation takes
> 45–90 minutes of Slack threads across 3 teams with 4 tool logins.
> With Elastic, the AI Agent answered in one conversation thread —
> accessible to the NOC, the CISO, and the field engineer's manager
> without additional tool licenses.

---

## Step 5 — Validate with ES|QL

In the **Elastic Serverless** tab, navigate to **Discover** and try ES|QL
to confirm the 5-signal correlation:

```sql
FROM logs-*, metrics-*
| WHERE user.name == "jsmith" OR network.site == "Midland-Field-Ops"
| WHERE @timestamp > NOW() - 30 minutes
| STATS
    snmp_events    = COUNT_IF(snmp.trap.type == "linkDown"),
    auth_failures  = COUNT_IF(winlog.event_id == 4625),
    appgate_denies = COUNT_IF(appgate.deny.reason IS NOT NULL),
    avd_reconnects = COUNT_IF(session.reconnect_count > 0)
| EVAL root_cause = CASE(
    snmp_events > 0 AND auth_failures > 3, "JITTER_DNS",
    appgate_denies > 0, "APPGATE_POLICY",
    "AWS_FALLBACK"
  )
```

> **This single query** spans ThousandEyes (SNMP), Windows Event Log,
> AppGate audit, and AVD metrics — correlating what four separate tools
> see independently. Exxon has never had this query before.

---

## Why This Matters for Exxon

| Before (4 siloed tools) | After (Elastic Serverless) |
|---|---|
| 45–90 min cross-team Slack investigation | 5 min AI Agent conversation |
| WAN team owns ThousandEyes — app team can't see it | ThousandEyes integrated into shared Kibana |
| Security team owns AppGate — desktop team can't see it | AppGate + iboss in same index as AVD metrics |
| Windows events in Splunk — no correlation to circuit data | `user.name` joins all five signal types in ES|QL |
| Multiple storage costs (Splunk, Datadog, ThousandEyes) | One Elastic Serverless project, one retention policy |

---

## Congratulations — Infrastructure 2.0 on Elastic

You have now completed all three challenges:

1. **OTel Unified APM** — Replaced Datadog APM + Splunk log pipelines with
   native OTel ingest. All 1,000+ Azure API service instances visible in one
   ES|QL query.

2. **SNMP Network Integration** — Brought Cisco WAN events out of OpenNMS and
   into the same platform as application data, enriched with ServiceNow CMDB
   and correlated with ThousandEyes agent IDs.

3. **End-User Experience Single Pane** — Answered "How is the machine
   functioning for the user?" in 5 minutes instead of 90, using `user.name`
   as the universal join key across AVD, Windows, iboss, AppGate, and
   ThousandEyes.

> **"All the messages and logs per app in one dashboard"** — built on a
> single Elastic Serverless project with one bill, one retention policy,
> and zero Logstash pipelines.
