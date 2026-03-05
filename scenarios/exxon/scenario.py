"""Exxon Infrastructure 2.0 scenario — Elastic Serverless observability pitch.

Maps Exxon's real environment (Azure API services, OpenShift K8s, Cisco WAN,
Azure Virtual Desktop) with fault channels that mirror their actual pain points:
fragmented Datadog/Splunk pipelines, SNMP-only network visibility, and
cross-team EUX investigations.
"""

from __future__ import annotations

import random
import time
from typing import Any

from scenarios.base import BaseScenario, CountdownConfig, UITheme


class ExxonScenario(BaseScenario):
    """Exxon Infrastructure 2.0 — Elastic Serverless unified observability."""

    # ── Identity ──────────────────────────────────────────────────────────────

    @property
    def scenario_id(self) -> str:
        return "exxon"

    @property
    def scenario_name(self) -> str:
        return "Exxon Infrastructure 2.0"

    @property
    def scenario_description(self) -> str:
        return (
            "Unified observability for Exxon's Azure API services, OpenShift "
            "Kubernetes, Cisco WAN infrastructure, and Azure Virtual Desktop "
            "fleet. Replacing Datadog, Splunk, OpenNMS, and ThousandEyes with "
            "a single Elastic Serverless project."
        )

    @property
    def namespace(self) -> str:
        return "exxon"

    # ── Services ──────────────────────────────────────────────────────────────
    # Maps Exxon's real Azure API services and supporting infrastructure.
    # service.name in OTel → Elastic APM service map node.

    @property
    def services(self) -> dict[str, dict[str, Any]]:
        return {
            # Azure API Services (the 1,000-instance estate, represented by key gateway)
            "api-gateway": {
                "cloud_provider": "azure",
                "cloud_region": "southcentralus",
                "cloud_platform": "azure_app_service",
                "cloud_availability_zone": "southcentralus-1",
                "subsystem": "api",
                "language": "java",
            },
            "payment-processor": {
                "cloud_provider": "azure",
                "cloud_region": "southcentralus",
                "cloud_platform": "azure_app_service",
                "cloud_availability_zone": "southcentralus-2",
                "subsystem": "api",
                "language": "dotnet",
            },
            "inventory-service": {
                "cloud_provider": "azure",
                "cloud_region": "southcentralus",
                "cloud_platform": "azure_app_service",
                "cloud_availability_zone": "southcentralus-3",
                "subsystem": "api",
                "language": "python",
            },
            # OpenShift / Kubernetes (container platform)
            "openshift-operator": {
                "cloud_provider": "azure",
                "cloud_region": "southcentralus",
                "cloud_platform": "azure_aks",
                "cloud_availability_zone": "southcentralus-1",
                "subsystem": "platform",
                "language": "go",
            },
            # Network & WAN
            "network-monitor": {
                "cloud_provider": "azure",
                "cloud_region": "southcentralus",
                "cloud_platform": "azure_vm",
                "cloud_availability_zone": "southcentralus-2",
                "subsystem": "network",
                "language": "python",
            },
            # Azure Virtual Desktop / End-User Experience
            "avd-broker": {
                "cloud_provider": "azure",
                "cloud_region": "southcentralus",
                "cloud_platform": "azure_vm",
                "cloud_availability_zone": "southcentralus-1",
                "subsystem": "desktop",
                "language": "dotnet",
            },
            # Security / Zero Trust
            "appgate-connector": {
                "cloud_provider": "azure",
                "cloud_region": "southcentralus",
                "cloud_platform": "azure_vm",
                "cloud_availability_zone": "southcentralus-2",
                "subsystem": "security",
                "language": "go",
            },
            # Identity / Auth
            "azure-ad-proxy": {
                "cloud_provider": "azure",
                "cloud_region": "southcentralus",
                "cloud_platform": "azure_vm",
                "cloud_availability_zone": "southcentralus-3",
                "subsystem": "identity",
                "language": "python",
            },
            # Data platform
            "data-ingestion": {
                "cloud_provider": "azure",
                "cloud_region": "eastus",
                "cloud_platform": "azure_app_service",
                "cloud_availability_zone": "eastus-1",
                "subsystem": "data",
                "language": "java",
            },
        }

    # ── Channel Registry ──────────────────────────────────────────────────────
    # 12 fault channels mapped directly to Exxon's pain points.
    # Each channel has a presenter narrative in its description.

    @property
    def channel_registry(self) -> dict[int, dict[str, Any]]:
        return {
            # ── API / APM Channels (1–4) ─────────────────────────────────────
            1: {
                "name": "Datadog Log Pipeline Failure",
                "subsystem": "api",
                "error_type": "pipeline_failure",
                "affected_services": ["api-gateway"],
                "cascade_services": ["payment-processor", "inventory-service"],
                "description": (
                    "Datadog log pipeline fails to create for api-gateway. "
                    "Traces land in Datadog but application logs are dropped — "
                    "the exact issue Exxon is experiencing today. "
                    "In Elastic Serverless: a single OTLP exporter URL replaces "
                    "this pipeline with zero configuration."
                ),
                "log_messages": [
                    "ERROR DatadogAgent - Log pipeline creation failed: upstream indexer rejected batch (HTTP 413)",
                    "WARN  DatadogAgent - Retrying log pipeline init (attempt 3/5): connection refused to dd-intake.datadoghq.com",
                    "ERROR DatadogAgent - Log pipeline permanently failed. Dropping 4,821 log records.",
                    "ERROR ApiGateway   - Telemetry gap detected: logs missing from T-00:05:00 to T-00:00:00",
                    "WARN  ApiGateway   - Falling back to stdout logging only — observability degraded",
                ],
                "stack_trace": (
                    "DatadogPipelineException: Failed to initialize log pipeline\n"
                    "  at dd_agent.pipeline.LogPipeline.init(pipeline.py:142)\n"
                    "  at dd_agent.runner.AgentRunner.start_pipelines(runner.py:89)\n"
                    "Caused by: ConnectionRefusedError: [Errno 111] Connection refused\n"
                    "  dd-intake.datadoghq.com:443"
                ),
                "remediation_action": "Switch OTLP exporter URL from Datadog endpoint to Elastic Serverless OTLP endpoint. No pipeline config required.",
            },
            2: {
                "name": "OTel Collector Orphaned — Nobody Owns It",
                "subsystem": "api",
                "error_type": "config_drift",
                "affected_services": ["api-gateway", "payment-processor"],
                "cascade_services": ["openshift-operator"],
                "description": (
                    "The OTel collector config was last updated 6 months ago and "
                    "is pointing at a decommissioned Datadog endpoint. Traces from "
                    "payment-processor are not reaching any backend. "
                    "'Nobody knows what to do with OpenTelemetry.'"
                ),
                "log_messages": [
                    "ERROR otelcol/exporter/datadog - Export failed: 401 Unauthorized (API key revoked)",
                    "WARN  otelcol/exporter/datadog - Dropping 12,450 spans — exporter queue overflow",
                    "ERROR PaymentProcessor - Trace context lost: no active span (orphaned collector)",
                    "ERROR otelcol/receiver/otlp  - Buffer full: rejecting new spans from payment-processor",
                    "WARN  otelcol/processor/batch - Batch timeout exceeded; flushing partial batch",
                ],
                "stack_trace": (
                    "OtelExporterException: Cannot export spans — Datadog API key is invalid\n"
                    "  exporter/datadog.DatadogExporter.export(exporter.go:234)\n"
                    "  processor/batch.BatchProcessor.flush(batch.go:112)\n"
                    "Last successful export: 2025-08-14T11:22:00Z (>200 days ago)"
                ),
                "remediation_action": "Update otel-collector-config.yaml exporter URL to Elastic Serverless OTLP endpoint. Authorization header: ApiKey <elastic_api_key>.",
            },
            3: {
                "name": "Azure API Service Latency SLO Breach",
                "subsystem": "api",
                "error_type": "latency_spike",
                "affected_services": ["payment-processor"],
                "cascade_services": ["api-gateway", "inventory-service"],
                "description": (
                    "payment-processor p95 latency exceeds 500ms SLO. "
                    "This is the type of cross-service impact that requires "
                    "correlating APM traces with OpenShift pod CPU — impossible "
                    "when Datadog and Splunk are separate tools."
                ),
                "log_messages": [
                    "ERROR PaymentProcessor - SLO breach: p95_latency=847ms threshold=500ms",
                    "WARN  PaymentProcessor - Connection pool exhausted: max=100 active=100 waiting=23",
                    "ERROR PaymentProcessor - Upstream timeout after 30000ms: inventory-service not responding",
                    "WARN  ApiGateway       - Circuit breaker OPEN for payment-processor (5 consecutive failures)",
                    "ERROR PaymentProcessor - Database connection pool timeout: all 50 connections in use",
                ],
                "stack_trace": (
                    "PaymentTimeoutException: Upstream call timed out after 30000ms\n"
                    "  payment.service.UpstreamClient.call(UpstreamClient.java:89)\n"
                    "  payment.service.PaymentService.processTransaction(PaymentService.java:156)\n"
                    "  payment.api.PaymentController.POST /api/v2/transaction(PaymentController.java:44)\n"
                    "Caused by: java.net.SocketTimeoutException: Read timed out"
                ),
                "remediation_action": "Scale OpenShift pod replica count for payment-processor. Check CPU throttling via Elastic APM → Infrastructure correlation.",
            },
            4: {
                "name": "Splunk Log Forwarder Gap",
                "subsystem": "api",
                "error_type": "log_gap",
                "affected_services": ["inventory-service"],
                "cascade_services": ["api-gateway"],
                "description": (
                    "Splunk Universal Forwarder for inventory-service dropped a "
                    "30-minute window of logs during index rollover. "
                    "No alerting fired because OpenNMS doesn't monitor Splunk "
                    "and Datadog doesn't have Splunk visibility."
                ),
                "log_messages": [
                    "ERROR SplunkForwarder - Index rollover failure: target index exxon-app-logs-2026 full",
                    "WARN  SplunkForwarder - Log buffer overflow: dropping oldest events (30-minute gap)",
                    "ERROR SplunkForwarder - Failed to reconnect to Splunk indexer after 15 retries",
                    "WARN  InventoryService - Audit log gap detected: compliance alert triggered",
                    "ERROR InventoryService - Cannot write to Splunk HEC: 503 Service Unavailable",
                ],
                "stack_trace": (
                    "SplunkHECException: HTTP 503 Service Unavailable from Splunk HEC endpoint\n"
                    "  splunk.forwarder.HECClient.send(HECClient.py:78)\n"
                    "  splunk.forwarder.LogRouter.route(LogRouter.py:134)\n"
                    "Lost 18,230 log records covering 2026-03-05T07:15:00Z–07:45:00Z"
                ),
                "remediation_action": "Replace Splunk HEC forwarder with Elastic Agent. OTLP ingest has no index capacity limits on Elastic Serverless.",
            },
            # ── Network / SNMP Channels (5–8) ────────────────────────────────
            5: {
                "name": "Cisco Circuit Flap — Houston Refinery",
                "subsystem": "network",
                "error_type": "link_flap",
                "affected_services": ["network-monitor"],
                "cascade_services": ["api-gateway", "avd-broker"],
                "description": (
                    "GigabitEthernet0/47 on cisco-sw-houston-01 is flapping. "
                    "OpenNMS sees the SNMP linkDown trap, but the app team watching "
                    "Datadog has no visibility. Elastic SNMP integration puts "
                    "network and APM events in the same platform."
                ),
                "log_messages": [
                    "TRAP  snmpd - linkDown: cisco-sw-houston-01 GigabitEthernet0/47 ifOperStatus=down",
                    "TRAP  snmpd - linkUp:   cisco-sw-houston-01 GigabitEthernet0/47 ifOperStatus=up (recovered after 12s)",
                    "TRAP  snmpd - linkDown: cisco-sw-houston-01 GigabitEthernet0/47 ifOperStatus=down (second flap)",
                    "WARN  OpenNMS - Circuit flapping detected: cisco-sw-houston-01 (3 state changes in 5 min)",
                    "ERROR ApiGateway - Upstream connection reset: 10.52.1.1 (Houston-Refinery-Campus)",
                ],
                "stack_trace": (
                    "SNMPTrapEvent: linkDown OID .1.3.6.1.6.3.1.1.5.3\n"
                    "  sysDescr: cisco-sw-houston-01 (Cisco IOS 15.2)\n"
                    "  ifIndex: 47 (GigabitEthernet0/47)\n"
                    "  ifOperStatus: 2 (down)\n"
                    "  community: exxon-public\n"
                    "CMDB: site=Houston-Refinery-Campus owner=exxon-infrastructure-2.0-team"
                ),
                "remediation_action": "Notify WAN team. Check ThousandEyes agent TE-HOU-001 for packet loss on Houston-MPLS-to-Azure path.",
            },
            6: {
                "name": "Midland MPLS Circuit Degradation",
                "subsystem": "network",
                "error_type": "circuit_degradation",
                "affected_services": ["network-monitor"],
                "cascade_services": ["avd-broker", "azure-ad-proxy"],
                "description": (
                    "ThousandEyes agent TE-MID-001 on cisco-sw-midland-03 detects "
                    "jitter > 45ms on the Midland-MPLS-to-Azure path. "
                    "This is the root cause of AVD session instability for Midland "
                    "field engineers — but today the WAN team and desktop team "
                    "never see the same dashboard."
                ),
                "log_messages": [
                    "WARN  ThousandEyes - Agent TE-MID-001: jitter=47.2ms (threshold=20ms) on Midland-MPLS-to-Azure",
                    "WARN  ThousandEyes - Agent TE-MID-001: packet_loss=3.1% dns_rtt=142ms",
                    "ERROR avd-broker  - Session reconnect storm: 14 users reconnected in 60s from Midland site",
                    "WARN  azure-ad-proxy - Auth timeout: LDAP lookup exceeded 5000ms threshold (DNS jitter)",
                    "ERROR avd-broker  - AVD health check failed for avd-mid-pool: host avd-mid-w10-042 unreachable",
                ],
                "stack_trace": (
                    "ThousandEyesAlert: Circuit jitter SLA breach\n"
                    "  agent: TE-MID-001 (Midland-MPLS-to-Azure)\n"
                    "  jitter_ms: 47.2 (threshold: 20)\n"
                    "  loss_pct: 3.1\n"
                    "  dns_rtt_ms: 142\n"
                    "  affected_site: Midland-Field-Ops\n"
                    "  affected_users: jsmith, tmorales (+12 others)"
                ),
                "remediation_action": "Escalate to WAN team for MPLS circuit investigation. Short-term: route Midland AVD traffic via backup AWS transit. Long-term: set ThousandEyes jitter > 20ms → Elastic alert rule.",
            },
            7: {
                "name": "OpenNMS SNMP Collection Gap",
                "subsystem": "network",
                "error_type": "collection_gap",
                "affected_services": ["network-monitor"],
                "cascade_services": [],
                "description": (
                    "OpenNMS failed to collect SNMP metrics from 3 Corpus Christi "
                    "switches for 2 hours. The gap is invisible to application "
                    "teams. Elastic Agent with SNMP integration would have "
                    "surfaced this as an alert alongside the APM data."
                ),
                "log_messages": [
                    "ERROR OpenNMS - SNMP collection failed: cisco-sw-corpus-01 (timeout after 30s)",
                    "ERROR OpenNMS - SNMP collection failed: cisco-sw-corpus-02 (no route to host)",
                    "WARN  OpenNMS - Poller thread exhausted: 48/48 threads active, queuing",
                    "ERROR OpenNMS - 2-hour collection gap: Corpus-Christi-Refinery nodes (3 devices)",
                    "WARN  OpenNMS - Alert suppressed: notification storm protection activated",
                ],
                "stack_trace": (
                    "OpenNMSCollectionException: SNMP timeout for cisco-sw-corpus-01\n"
                    "  OID: .1.3.6.1.2.1.2.2.1 (ifTable)\n"
                    "  community: exxon-public\n"
                    "  timeout_ms: 30000\n"
                    "  retries: 3\n"
                    "Data gap: 2026-03-05T06:15:00Z–08:15:00Z (2h)"
                ),
                "remediation_action": "Deploy Elastic Agent with SNMP integration on OpenNMS host. Data gaps become visible as missing heartbeat events in Elastic Serverless.",
            },
            8: {
                "name": "ThousandEyes–Datadog Correlation Gap",
                "subsystem": "network",
                "error_type": "tool_silos",
                "affected_services": ["network-monitor", "api-gateway"],
                "cascade_services": ["avd-broker"],
                "description": (
                    "ThousandEyes reports latency spike on Azure ExpressRoute edge. "
                    "Datadog shows increased error rate on api-gateway. "
                    "The two events are correlated but neither tool knows about the "
                    "other — requiring a manual war room to connect the dots. "
                    "Elastic Serverless correlates both via shared network.site tag."
                ),
                "log_messages": [
                    "WARN  ThousandEyes - Agent TE-AZ-001: latency=210ms on Azure-ExpressRoute-Edge (baseline=45ms)",
                    "ERROR Datadog      - api-gateway error_rate=8.2% (SLO threshold=2%)",
                    "WARN  Datadog      - No correlated network event found (ThousandEyes not in Datadog scope)",
                    "ERROR ApiGateway   - 503 errors spiking: downstream Azure services unreachable",
                    "WARN  SRE-Oncall   - War room opened: Slack #exxon-p1-incident (manual correlation required)",
                ],
                "stack_trace": (
                    "CorrelationGap: ThousandEyes event has no Datadog counterpart\n"
                    "  thousandeyes.agent: TE-AZ-001\n"
                    "  thousandeyes.event: latency_spike at 2026-03-05T07:30:00Z\n"
                    "  datadog.metric: api_gateway.error_rate spike at 2026-03-05T07:31:00Z\n"
                    "  time_to_correlate: 47 minutes (manual war room)"
                ),
                "remediation_action": "Elastic Serverless: ThousandEyes integration + APM traces share thousandeyes.agent_id and network.site. ES|QL correlates in milliseconds.",
            },
            # ── End-User Experience Channels (9–12) ──────────────────────────
            9: {
                "name": "AppGate Device Certificate Expired",
                "subsystem": "security",
                "error_type": "cert_expiry",
                "affected_services": ["appgate-connector"],
                "cascade_services": ["avd-broker", "azure-ad-proxy"],
                "description": (
                    "AppGate Zero Trust denies 'Audit-System-Access' entitlement "
                    "for AVD host avd-mid-w10-042: device certificate expired. "
                    "iboss also blocks audit.exxon.internal on the same path. "
                    "Without Elastic, this takes 45+ minutes to diagnose across "
                    "three teams with three tools."
                ),
                "log_messages": [
                    "ERROR AppGate - DENY Audit-System-Access: avd-mid-w10-042 jsmith@exxon.com — device cert expired",
                    "ERROR iboss   - BLOCKED audit.exxon.internal: device posture check failed (cert expired)",
                    "ERROR AppGate - DENY Audit-System-Access: avd-mid-w10-042 jsmith@exxon.com — device cert expired (retry)",
                    "WARN  avd-broker - Session degraded: jsmith@exxon.com — appgate connectivity failure",
                    "ERROR azure-ad-proxy - Kerberos TGT refresh failed for jsmith: AppGate tunnel down",
                ],
                "stack_trace": (
                    "AppGatePolicyException: Entitlement denied\n"
                    "  user: jsmith@exxon.com\n"
                    "  host: avd-mid-w10-042\n"
                    "  entitlement: Audit-System-Access\n"
                    "  policy: exxon-audit-internal-policy\n"
                    "  deny_reason: Device certificate expired\n"
                    "  cert_expiry: 2026-02-28T00:00:00Z (5 days ago)\n"
                    "  action_required: Re-enroll device in Microsoft Intune"
                ),
                "remediation_action": "Re-enroll avd-mid-w10-042 device certificate via Microsoft Intune (SCCM push available). AppGate entitlement will auto-restore on cert renewal.",
            },
            10: {
                "name": "Azure Virtual Desktop Session Storm",
                "subsystem": "desktop",
                "error_type": "session_degradation",
                "affected_services": ["avd-broker"],
                "cascade_services": ["azure-ad-proxy", "appgate-connector"],
                "description": (
                    "14 Midland field engineers report AVD sessions disconnecting. "
                    "Logon times exceed 30 seconds (normal: <5s). "
                    "Root cause: Midland MPLS jitter + AppGate cert issue compounding. "
                    "Elastic Serverless surfaces the full picture via user.name join key."
                ),
                "log_messages": [
                    "ERROR avd-broker - Session reconnect storm: 14 users, 47 reconnects in 90s (Midland site)",
                    "WARN  avd-broker - avd-mid-w10-042: logon_duration=38400ms (SLO: 5000ms) jsmith",
                    "WARN  avd-broker - avd-mid-w10-043: logon_duration=29100ms tmorales",
                    "ERROR avd-broker - Profile load failure: jsmith — FSLogix container mount timeout",
                    "WARN  avd-broker - Pool health: avd-mid-pool 14/20 sessions degraded",
                ],
                "stack_trace": (
                    "AVDSessionException: Profile load timeout\n"
                    "  user: jsmith@exxon.com\n"
                    "  host: avd-mid-w10-042\n"
                    "  pool: avd-mid-pool (Midland-Field-Ops)\n"
                    "  logon_duration_ms: 38400 (SLO: 5000)\n"
                    "  fslogix_error: VHD mount timeout after 30s\n"
                    "  contributing_factors: MPLS jitter (47ms), AppGate cert expired"
                ),
                "remediation_action": "1. Fix AppGate cert (channel 9). 2. WAN team route Midland via AWS backup. 3. AVD team increase FSLogix mount timeout to 60s while MPLS issue resolves.",
            },
            11: {
                "name": "Windows Event ID 4625 Storm — Jitter DNS Auth Failure",
                "subsystem": "identity",
                "error_type": "auth_failure_storm",
                "affected_services": ["azure-ad-proxy"],
                "cascade_services": ["avd-broker", "appgate-connector"],
                "description": (
                    "DNS RTT jitter on Midland MPLS causes Azure AD authentication "
                    "timeouts, generating a storm of Event ID 4625 (logon failure). "
                    "Account lockout policies engage after 3 failures. "
                    "This is 'Jitter DNS' — Exxon's internal term for a known WAN issue."
                ),
                "log_messages": [
                    "ERROR WinEventLog - EventID:4625 Audit Failure jsmith@exxon.com — Unknown user name or bad password (DNS timeout)",
                    "ERROR WinEventLog - EventID:4625 Audit Failure jsmith@exxon.com — account locked after 3 failures",
                    "WARN  azure-ad-proxy - Kerberos auth latency: 8200ms (DNS RTT jitter on MPLS path)",
                    "ERROR azure-ad-proxy - LDAP bind failed: timeout after 5000ms — DNS RTT=142ms on Midland WAN",
                    "ERROR WinEventLog - EventID:4740 Account Locked Out: jsmith@exxon.com",
                ],
                "stack_trace": (
                    "KerberosAuthException: Authentication timeout\n"
                    "  user: jsmith@exxon.com\n"
                    "  dc: dc01.exxon.internal\n"
                    "  dns_rtt_ms: 142 (threshold: 50)\n"
                    "  ldap_timeout_ms: 5000\n"
                    "  win_event_id: 4625 (×3) → 4740 (account lockout)\n"
                    "  root_cause: Jitter DNS — MPLS WAN RTT spike (TE-MID-001)"
                ),
                "remediation_action": "1. Unlock jsmith account in Active Directory. 2. Notify WAN team of DNS jitter pattern (ThousandEyes TE-MID-001 > 20ms). 3. Set Elastic alert: winlog.event_id=4625 count > 3 in 5min → page WAN team.",
            },
            12: {
                "name": "iboss Zero Trust Policy Misconfiguration",
                "subsystem": "security",
                "error_type": "policy_block",
                "affected_services": ["appgate-connector"],
                "cascade_services": ["avd-broker"],
                "description": (
                    "An iboss policy update pushed to 'exxon-internal-app-policy' "
                    "incorrectly blocks audit.exxon.internal for Midland devices. "
                    "The policy was meant to block public cloud storage only. "
                    "Without Elastic, the security team doesn't know which users "
                    "are affected until support tickets arrive."
                ),
                "log_messages": [
                    "ERROR iboss - BLOCKED audit.exxon.internal: policy exxon-internal-app-policy (policy update 2026-03-04T22:00Z)",
                    "ERROR iboss - BLOCKED audit.exxon.internal: jsmith@exxon.com avd-mid-w10-042 (×3)",
                    "WARN  iboss - Policy change audit: exxon-internal-app-policy modified by admin@exxon.com",
                    "ERROR iboss - 47 users blocked from audit.exxon.internal in last 60 minutes",
                    "WARN  AppGate - Correlated iboss block with AppGate DENY for same destination",
                ],
                "stack_trace": (
                    "ibossPolicyBlock: Destination blocked by enterprise policy\n"
                    "  destination: audit.exxon.internal\n"
                    "  policy: exxon-internal-app-policy\n"
                    "  block_reason: Destination not in approved enterprise tunnel path\n"
                    "  policy_version: 2026-03-04T22:00:00Z\n"
                    "  affected_users: 47 (Midland, Corpus Christi sites)\n"
                    "  false_positive: policy should only block *.blob.core.windows.net"
                ),
                "remediation_action": "Revert iboss policy exxon-internal-app-policy to previous version. Add audit.exxon.internal to the approved tunnel whitelist. Elastic alert: iboss.event.outcome=blocked on internal domains → immediate security team page.",
            },
        }

    # ── Theme ─────────────────────────────────────────────────────────────────
    # Exxon corporate colors: dark background, red accent.

    @property
    def theme(self) -> UITheme:
        return UITheme(
            bg_primary="#0a0a0a",
            bg_secondary="#111111",
            bg_tertiary="#1a1a1a",
            accent_primary="#EE0000",      # Exxon red
            accent_secondary="#00bfb3",    # Elastic teal (co-brand)
            text_primary="#f0f0f0",
            text_secondary="#999999",
            text_accent="#EE0000",
            status_nominal="#22c55e",
            status_warning="#f59e0b",
            status_critical="#EE0000",
            dashboard_title="Exxon Infrastructure 2.0 — Elastic Serverless",
            chaos_title="Exxon Fault Injection Console",
            landing_title="Exxon Infrastructure 2.0",
            font_family="'Inter', 'Segoe UI', system-ui, sans-serif",
            font_mono="'JetBrains Mono', 'Cascadia Code', monospace",
            scanline_effect=False,
            glow_effect=False,
            grid_background=False,
            gradient_accent=True,
        )

    # ── Countdown ─────────────────────────────────────────────────────────────
    # No countdown for this demo — it's a persistent observability pitch.

    @property
    def countdown_config(self) -> CountdownConfig:
        return CountdownConfig(enabled=False, start_seconds=0, speed=1.0)

    # ── Service Topology ──────────────────────────────────────────────────────

    @property
    def service_topology(self) -> dict[str, list[str]]:
        return {
            "api-gateway": ["payment-processor", "inventory-service"],
            "payment-processor": ["data-ingestion", "azure-ad-proxy"],
            "inventory-service": ["data-ingestion"],
            "openshift-operator": ["api-gateway", "payment-processor", "inventory-service"],
            "network-monitor": ["api-gateway", "avd-broker"],
            "avd-broker": ["azure-ad-proxy", "appgate-connector"],
            "appgate-connector": ["azure-ad-proxy"],
            "azure-ad-proxy": [],
            "data-ingestion": [],
        }

    @property
    def entry_endpoints(self) -> list[str]:
        return ["api-gateway", "avd-broker"]

    # ── Hosts ─────────────────────────────────────────────────────────────────

    @property
    def hosts(self) -> list[dict[str, str]]:
        return [
            {"hostname": "azure-api-node-01", "os": "linux", "cloud_provider": "azure", "cloud_region": "southcentralus"},
            {"hostname": "azure-api-node-02", "os": "linux", "cloud_provider": "azure", "cloud_region": "southcentralus"},
            {"hostname": "openshift-worker-01", "os": "linux", "cloud_provider": "azure", "cloud_region": "southcentralus"},
            {"hostname": "openshift-worker-02", "os": "linux", "cloud_provider": "azure", "cloud_region": "southcentralus"},
            {"hostname": "cisco-sw-houston-01", "os": "cisco_ios", "cloud_provider": "on-prem", "cloud_region": "us-south"},
            {"hostname": "cisco-sw-midland-03", "os": "cisco_ios", "cloud_provider": "on-prem", "cloud_region": "us-west"},
            {"hostname": "avd-mid-w10-042", "os": "windows", "cloud_provider": "azure", "cloud_region": "southcentralus"},
            {"hostname": "avd-hou-w10-101", "os": "windows", "cloud_provider": "azure", "cloud_region": "southcentralus"},
        ]

    # ── Kubernetes Clusters ───────────────────────────────────────────────────

    @property
    def k8s_clusters(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "openshift-prod",
                "provider": "azure",
                "platform": "azure_aks",
                "region": "southcentralus",
                "namespace": "exxon-infrastructure",
                "zones": ["southcentralus-1", "southcentralus-2", "southcentralus-3"],
                "os_description": "Red Hat Enterprise Linux CoreOS 4.14",
                "services": ["api-gateway", "payment-processor", "inventory-service", "openshift-operator"],
            },
            {
                "name": "openshift-dev",
                "provider": "azure",
                "platform": "azure_aks",
                "region": "eastus",
                "namespace": "exxon-dev",
                "zones": ["eastus-1", "eastus-2"],
                "os_description": "Red Hat Enterprise Linux CoreOS 4.14",
                "services": ["network-monitor", "avd-broker"],
            },
        ]

    # ── Agent Config ──────────────────────────────────────────────────────────

    @property
    def agent_config(self) -> dict[str, Any]:
        return {
            "name": "exxon-infrastructure-analyst",
            "description": (
                "AI observability analyst for Exxon Infrastructure 2.0. "
                "Specialises in correlating APM traces from Azure API services, "
                "SNMP network events from Cisco WAN infrastructure, AppGate Zero "
                "Trust audit logs, and Azure Virtual Desktop session metrics. "
                "Use ES|QL to join data across service.name, user.name, and "
                "network.site to answer 'How is the machine functioning for the user?'"
            ),
            "instructions": (
                "You are an observability analyst for Exxon Infrastructure 2.0, "
                "running on Elastic Serverless. Your role is to:\n"
                "1. Correlate APM traces (traces-apm-*) with container metrics "
                "(metrics-kubernetes.*) using service.name as the join key.\n"
                "2. Correlate SNMP network events (logs-snmp.*) with ServiceNow CMDB "
                "data using device.hostname and network.site.\n"
                "3. Investigate end-user experience issues by joining AVD metrics, "
                "Windows event logs, iboss connection logs, AppGate audit logs, and "
                "ThousandEyes circuit data on user.name and host.name.\n"
                "4. Determine root cause from: AWS fallback latency, Jitter DNS "
                "(WAN MPLS jitter > 20ms causing auth timeouts), or AppGate Zero "
                "Trust policy blocks (device cert expired).\n"
                "Always cite the ES|QL query used and explain which tool it replaces "
                "(Datadog, Splunk, OpenNMS, or ThousandEyes)."
            ),
        }

    # ── Knowledge Base ────────────────────────────────────────────────────────

    @property
    def knowledge_base_docs(self) -> list[dict[str, str]]:
        return [
            {
                "title": "Exxon Infrastructure 2.0 — Tool Replacement Map",
                "content": (
                    "Datadog APM → Elastic Serverless OTLP traces (traces-apm-*)\n"
                    "Splunk app logs → Elastic Agent / OTLP logs (logs-apm-*)\n"
                    "OpenNMS SNMP → Elastic SNMP integration (logs-snmp.*)\n"
                    "ThousandEyes → Elastic ThousandEyes integration (logs-thousandeyes.*)\n"
                    "Manual CMDB → Elastic enrich policy on exxon-cmdb-devices index\n"
                    "AppGate / iboss → Elastic Agent custom logs (logs-appgate.*, logs-iboss.*)\n"
                    "AVD metrics → Elastic Azure integration (metrics-azure.app_service.*)\n"
                    "Windows events → Elastic Agent Windows integration (logs-windows.*)"
                ),
            },
            {
                "title": "Jitter DNS — Exxon WAN Known Issue",
                "content": (
                    "Jitter DNS is Exxon's internal term for elevated DNS resolution "
                    "latency caused by MPLS WAN jitter on the Midland-to-Azure circuit. "
                    "When ThousandEyes agent TE-MID-001 reports jitter > 20ms, Azure AD "
                    "authentication begins timing out (LDAP bind > 5000ms), causing Windows "
                    "Event ID 4625 (logon failure) storms. After 3 failures, accounts are "
                    "locked (Event ID 4740). WAN team escalation + DNS TTL reduction resolves."
                ),
            },
            {
                "title": "AppGate Zero Trust — Device Certificate Policy",
                "content": (
                    "AppGate requires a valid device certificate for the 'Audit-System-Access' "
                    "entitlement. Certificates are issued by Microsoft Intune and expire after "
                    "90 days. When expired, AppGate denies the entitlement and iboss also blocks "
                    "audit.exxon.internal. Resolution: SCCM push to re-enroll device cert via "
                    "Intune. The Elastic appgate.deny.reason field surfaces this immediately."
                ),
            },
            {
                "title": "ES|QL Correlation Cheatsheet",
                "content": (
                    "APM + K8s: FROM traces-apm-*, metrics-kubernetes.* | LOOKUP ON service.name\n"
                    "SNMP + CMDB: FROM logs-snmp.trap-exxon | ENRICH exxon-cmdb-enrich ON device.hostname\n"
                    "EUX 5-signal: FROM logs-windows.*, logs-iboss.*, logs-appgate.*, logs-thousandeyes.*, metrics-azure.avd.* | WHERE user.name == 'jsmith'\n"
                    "Network impact: FROM logs-snmp.trap-exxon | WHERE event.type == 'linkDown' | STATS COUNT(*) BY network.site, application.owner"
                ),
            },
        ]


    # ── Service classes ───────────────────────────────────────────────────────
    # Returns [] so the generic log generators handle telemetry; no space-themed
    # service classes needed for Exxon.

    def get_service_classes(self) -> list[type]:
        return []

    # ── Fault parameters ──────────────────────────────────────────────────────
    # Provides Exxon-specific values consumed by chaos injection logic.

    def get_fault_params(self, channel: int) -> dict[str, Any]:
        return {
            # OTel / APM
            "error_rate_pct":      round(random.uniform(5.0, 25.0), 1),
            "latency_p95_ms":      random.randint(800, 8000),
            "pipeline_name":       random.choice(["datadog-log-ingest", "splunk-hec-forward", "otel-collector-azure"]),
            "service_name":        random.choice(["api-gateway", "payment-processor", "inventory-service"]),
            "dropped_spans":       random.randint(50, 2000),
            # SNMP / network
            "device_hostname":     random.choice(["cisco-sw-houston-01", "cisco-sw-midland-03", "cisco-sw-corpus-02"]),
            "interface":           random.choice(["GigabitEthernet0/47", "TenGigabitEthernet1/0/1", "GigabitEthernet0/23"]),
            "snmp_trap_type":      random.choice(["linkDown", "linkDown", "linkUp"]),
            "circuit_jitter_ms":   round(random.uniform(20.0, 80.0), 1),
            "circuit_loss_pct":    round(random.uniform(1.0, 8.0), 1),
            "circuit_latency_ms":  random.randint(45, 200),
            # AppGate / Zero Trust
            "device_cert_days":    random.randint(0, 5),
            "entitlement":         random.choice(["Audit-System-Full-Access", "Field-Data-Access", "Corporate-VPN"]),
            "appgate_policy":      random.choice(["Field-Engineer-Standard", "Admin-Elevated", "Contractor"]),
            # AVD / EUX
            "avd_host":            random.choice(["avd-mid-w10-042", "avd-hou-w10-011", "avd-cor-w10-022"]),
            "user_name":           random.choice(["jsmith", "awilliams", "bgarcia"]),
            "logon_duration_s":    random.randint(20, 90),
            "reconnect_count":     random.randint(3, 15),
            "windows_event_id":    random.choice([4625, 4625, 7036, 1074]),
            # Generic
            "epoch":               int(time.time()) - random.randint(60, 3600),
            "duration_ms":         random.randint(100, 30000),
            "threshold_ms":        5000,
            "site":                random.choice(["Houston-Refinery-Campus", "Midland-Field-Ops", "Corpus-Christi-Refinery"]),
        }

    # ── Assessment tool config ────────────────────────────────────────────────

    @property
    def assessment_tool_config(self) -> dict[str, Any]:
        return {
            "id": "exxon_infra2_assessment",
            "description": (
                "Infrastructure 2.0 unified observability assessment. Evaluates all "
                "Exxon services against observability maturity criteria: OTel coverage, "
                "SNMP-to-APM correlation, CMDB enrichment completeness, and EUX "
                "monitoring coverage for Azure Virtual Desktop fleet. "
                "Log message field: body.text (never use 'body' alone)."
            ),
        }

    # ── DB operations ─────────────────────────────────────────────────────────
    # Used by the MySQL log generator to simulate realistic query patterns.

    @property
    def db_operations(self) -> dict[str, list[tuple]]:
        return {
            "api-gateway": [
                ("SELECT", "api_routes",
                 "SELECT route_id, service_name, upstream_url FROM api_routes WHERE active = 1 AND region = ? LIMIT 50"),
                ("INSERT", "api_access_log",
                 "INSERT INTO api_access_log (trace_id, service, method, path, status, latency_ms, ts) VALUES (?, ?, ?, ?, ?, ?, NOW())"),
            ],
            "payment-processor": [
                ("SELECT", "transactions",
                 "SELECT txn_id, amount, currency, status FROM transactions WHERE created_at > ? AND status = 'pending' ORDER BY created_at DESC LIMIT 100"),
                ("UPDATE", "transactions",
                 "UPDATE transactions SET status = ?, updated_at = NOW() WHERE txn_id = ?"),
            ],
            "inventory-service": [
                ("SELECT", "inventory",
                 "SELECT item_id, sku, qty_available, location FROM inventory WHERE facility = ? AND qty_available > 0 LIMIT 200"),
                ("INSERT", "inventory_events",
                 "INSERT INTO inventory_events (item_id, event_type, delta_qty, operator, ts) VALUES (?, ?, ?, ?, NOW())"),
            ],
            "avd-broker": [
                ("SELECT", "avd_sessions",
                 "SELECT session_id, user_name, host_name, state, logon_ts FROM avd_sessions WHERE state = 'active' AND site = ?"),
                ("UPDATE", "avd_sessions",
                 "UPDATE avd_sessions SET last_seen = NOW(), reconnect_count = reconnect_count + 1 WHERE session_id = ?"),
            ],
            "network-monitor": [
                ("SELECT", "snmp_devices",
                 "SELECT device_id, hostname, ip, site, last_trap_ts FROM snmp_devices WHERE last_trap_ts > ? ORDER BY last_trap_ts DESC"),
                ("INSERT", "trap_events",
                 "INSERT INTO trap_events (device_id, trap_type, interface, oid, received_at) VALUES (?, ?, ?, ?, NOW())"),
            ],
        }


# Module-level singleton — imported by scenarios/__init__.py discovery
scenario = ExxonScenario()
