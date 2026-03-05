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

In this challenge, you will use the **pre-built unified Elastic dashboard**
to answer this question in under 5 minutes.

---

## Step 1 — Generate the Simulated EUX Dataset

The setup script has pre-generated one hour of simulated telemetry for
**user: `jsmith` on host: `avd-mid-w10-042`** — a field engineer's AVD
session from the Midland office. Start the dashboard server:

```bash
cd /root/exxon-eux
./start-dashboard.sh
```

Switch to the **Dashboard Preview** tab to open the Elastic-style dashboard.

Alternatively, explore the raw data files:

```bash
ls /root/exxon-eux/data/
```

You will find:
- `avd-metrics.json` — Azure Virtual Desktop session reliability metrics
- `windows-events.json` — Forwarded Windows Security and Application events
- `iboss-connections.json` — iboss connection log (allowed/blocked)
- `appgate-audit.json` — AppGate Zero Trust policy evaluation log
- `thousandeyes-metrics.json` — ThousandEyes circuit metrics (jitter, loss)

---

## Step 2 — Understand the Dashboard Panels

The unified dashboard has five panels, each mapping to a previous tool:

### Panel A — AVD Session Health (was: manual Desktop team checks)
Shows per-session metrics for all AVD hosts. Look at:
- `session.logon_duration_ms` — how long did the session take to start?
- `session.app_launch_ms` — application launch time
- `session.reconnect_count` — how many times did the session reconnect?

**Find user `jsmith` on host `avd-mid-w10-042`.**

```bash
cat /root/exxon-eux/data/avd-metrics.json | python3 -c "
import sys, json
data = [json.loads(l) for l in sys.stdin if l.strip()]
user = [d for d in data if d.get('user.name') == 'jsmith']
for d in user:
    print(f'  logon_duration: {d.get(\"session.logon_duration_ms\")}ms | app_launch: {d.get(\"session.app_launch_ms\")}ms | reconnects: {d.get(\"session.reconnect_count\")}')
"
```

> Note the logon duration and reconnect count — are these normal?

---

### Panel B — Windows Event Log (was: Splunk)

Review the forwarded Windows events for `jsmith`'s host:

```bash
cat /root/exxon-eux/data/windows-events.json | python3 -c "
import sys, json
data = [json.loads(l) for l in sys.stdin if l.strip()]
host = [d for d in data if d.get('host.name') == 'avd-mid-w10-042']
for d in sorted(host, key=lambda x: x.get('@timestamp','')):
    print(f'  [{d.get(\"@timestamp\",\"\")}] EventID:{d.get(\"winlog.event_id\")} - {d.get(\"message\",\"\")[:80]}')
"
```

Look for Event IDs:
- `4625` — Failed login (wrong credentials or auth failure)
- `6006` — Event log service stopped (unusual shutdown)
- `7036` — Service state changed
- `1074` — System restart initiated

> What do the event IDs tell you about the state of this machine?

---

### Panel C — iboss Connection Log (was: manual Security team query)

```bash
cat /root/exxon-eux/data/iboss-connections.json | python3 -c "
import sys, json
data = [json.loads(l) for l in sys.stdin if l.strip()]
user = [d for d in data if d.get('user.name') == 'jsmith']
blocked = [d for d in user if d.get('event.outcome') == 'blocked']
print(f'Total connections: {len(user)} | Blocked: {len(blocked)}')
for d in blocked[:5]:
    print(f'  BLOCKED → {d.get(\"destination.domain\",\"\")} | policy: {d.get(\"iboss.policy.name\",\"\")} | reason: {d.get(\"iboss.block.reason\",\"\")}')
"
```

---

### Panel D — AppGate Zero Trust Audit Log

```bash
cat /root/exxon-eux/data/appgate-audit.json | python3 -c "
import sys, json
data = [json.loads(l) for l in sys.stdin if l.strip()]
user = [d for d in data if d.get('user.name') == 'jsmith']
for d in user:
    print(f'  [{d.get(\"event.outcome\")}] Entitlement: {d.get(\"appgate.entitlement.name\")} | Policy: {d.get(\"appgate.policy.name\")} | Reason: {d.get(\"appgate.deny.reason\",\"ALLOW\")}')
"
```

> Is AppGate allowing or denying access? Which entitlement is being denied?

---

### Panel E — ThousandEyes Circuit Metrics (was: ThousandEyes UI, WAN team only)

```bash
cat /root/exxon-eux/data/thousandeyes-metrics.json | python3 -c "
import sys, json
data = [json.loads(l) for l in sys.stdin if l.strip()]
midland = [d for d in data if 'midland' in d.get('thousandeyes.agent.name','').lower()]
for d in midland:
    print(f'  [{d.get(\"@timestamp\",\"\")}] Agent: {d.get(\"thousandeyes.agent.name\")} | Loss: {d.get(\"thousandeyes.net.loss_pct\")}% | Jitter: {d.get(\"thousandeyes.net.jitter_ms\")}ms | DNS RTT: {d.get(\"thousandeyes.dns.rtt_ms\")}ms')
"
```

---

## Step 3 — The Root Cause Investigation

Based on the five panels, answer these questions by examining the data:

### Question 1: Is the issue caused by AWS fallback latency?

Look at the ThousandEyes circuit metrics (Panel E). If Exxon's MPLS circuit
to Azure is congested, traffic falls back to an AWS transit path, adding
**50–80ms of additional latency**.

Check: Is packet loss > 5% OR latency > 150ms in the Midland circuit?

```bash
# Quick check
python3 /root/exxon-eux/investigate.py --check aws-fallback --user jsmith
```

---

### Question 2: Is this Jitter DNS from the WAN team?

"Jitter DNS" is Exxon's internal term for a known issue where DNS resolution
jitter from the MPLS WAN causes Azure AD authentication to time out,
triggering Windows Event ID `4625` (login failure) even though credentials
are correct.

Check: Is DNS RTT jitter > 20ms AND are there Event ID `4625` events?

```bash
python3 /root/exxon-eux/investigate.py --check jitter-dns --user jsmith
```

---

### Question 3: Is this an AppGate Zero Trust policy block?

When AppGate denies an entitlement, the client-side application sees a
connection refused — indistinguishable from a network outage without the
audit log. Cross-reference the AppGate audit (Panel D) with the iboss
connection log (Panel C).

Check: Is the audit system (`audit.exxon.internal`) blocked by iboss OR
denied by AppGate?

```bash
python3 /root/exxon-eux/investigate.py --check appgate-block --user jsmith
```

---

## Step 4 — Identify the Root Cause

Run the full investigation and identify which of the three root causes
applies to `jsmith`'s session:

```bash
python3 /root/exxon-eux/investigate.py --full-report --user jsmith
```

The investigation script reads all five data files and produces a unified
timeline showing exactly when each signal changed — similar to what a
pre-built Elastic Timeline investigation would surface.

**Read the output carefully.** The root cause is one of:

- `AWS_FALLBACK` — Circuit congestion rerouted to AWS transit, adding latency
- `JITTER_DNS` — DNS resolution jitter from WAN caused auth timeouts
- `APPGATE_POLICY` — AppGate Zero Trust entitlement was denied by policy update

Record your finding. You will need it for the validation step.

---

## Step 5 — Write the ES|QL Correlation Query

Once you know the root cause, write the ES|QL query that would surface this
issue in a production Elastic Serverless environment. A template is provided:

```bash
cat /root/exxon-eux/queries/eux-investigation.esql
```

Review the template and understand how `user.name` and `host.name` serve as
the correlation keys across all five data streams.

---

## Step 6 — Validate

Run the validation script, specifying the root cause you identified:

```bash
/root/exxon-eux/check-eux-investigation.sh
```

The script verifies:
1. All five EUX data files exist and contain data
2. The investigation script runs successfully for user `jsmith`
3. A root cause has been identified from the simulated data

Successful output:

```
✓ AVD session metrics loaded        → N session records for jsmith
✓ Windows event log loaded          → N events for avd-mid-w10-042
✓ iboss connection log loaded        → N connections, M blocked
✓ AppGate Zero Trust audit loaded   → N policy evaluations
✓ ThousandEyes circuit data loaded  → N Midland circuit samples
✓ Root cause identified             → [ROOT_CAUSE]
✓ Challenge 3 complete — single pane of glass for end-user experience
```

---

## Why This Matters for Exxon

| Before (4 siloed tools) | After (Elastic Serverless) |
|---|---|
| 45–90 min cross-team Slack investigation | 5 min ES|QL timeline investigation |
| WAN team owns ThousandEyes — app team can't see it | ThousandEyes integrated into shared Kibana |
| Security team owns AppGate — desktop team can't see it | AppGate + iboss in same index as AVD metrics |
| Windows events in Splunk — no correlation to circuit data | `user.name` joins all five signal types in ES|QL |
| Multiple storage costs (Splunk ingest, Datadog hosts, ThousandEyes) | One Elastic Serverless project, one retention policy |

---

## Congratulations — Infrastructure 2.0 on Elastic

You have now completed all three challenges:

1. **OTel Unified APM** — Replaced Datadog APM + Splunk log pipelines with
   native OTel ingest. All 1,000 Azure API service instances visible in one
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
