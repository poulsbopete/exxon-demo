#!/usr/bin/env python3
"""Application Log Generator — sends structured app logs via OTLP to logs.otel.

Sends logs from Exxon's Azure API services WITHOUT data_stream.* resource
attributes, so Elastic Serverless routes them to the generic `logs.otel` stream.
This demonstrates native OTel application log ingest — traces, metrics, and
logs from the same services visible in one unified stream.

Usage (standalone):
    python3 -m log_generators.app_log_generator
"""

from __future__ import annotations

import logging
import random
import secrets
import signal
import threading
import time

from app.telemetry import OTLPClient, _format_attributes, SCHEMA_URL, _now_ns
from app.config import NAMESPACE

logger = logging.getLogger("app-log-generator")

BATCH_INTERVAL_MIN = 3
BATCH_INTERVAL_MAX = 8
BATCH_SIZE_MIN = 8
BATCH_SIZE_MAX = 30

# ── Exxon service log templates ───────────────────────────────────────────────

_SERVICE_LOGS: dict[str, list[tuple[str, str, dict]]] = {
    "api-gateway": [
        ("INFO",  "Request routed to payment-processor: POST /api/v2/transaction latency=42ms", {"http.request.method": "POST", "url.path": "/api/v2/transaction", "http.response.status_code": 200}),
        ("INFO",  "Health check passed: all upstream services reachable", {"event.kind": "event", "event.category": "web"}),
        ("WARN",  "Circuit breaker HALF-OPEN: payment-processor recovered after 3 failures", {"circuit_breaker.state": "half_open", "upstream.service": "payment-processor"}),
        ("ERROR", "Upstream timeout after 30000ms: inventory-service not responding", {"upstream.service": "inventory-service", "timeout.ms": "30000"}),
        ("INFO",  "Request routed to inventory-service: GET /api/v1/inventory/check latency=18ms", {"http.request.method": "GET", "url.path": "/api/v1/inventory/check", "http.response.status_code": 200}),
        ("WARN",  "Rate limit approaching: 920/1000 requests in last 60s from 10.0.1.42", {"rate_limit.current": "920", "rate_limit.max": "1000", "client.address": "10.0.1.42"}),
        ("ERROR", "SLO breach: error_rate=4.2% exceeds threshold=2% for api-gateway", {"slo.metric": "error_rate", "slo.current": "4.2", "slo.threshold": "2.0"}),
        ("INFO",  "OTLP trace exported: 128 spans to Elastic Serverless ingest endpoint", {"otlp.span_count": "128", "otlp.export.success": "true"}),
    ],
    "payment-processor": [
        ("INFO",  "Transaction processed: txn_id=TXN-88421 amount=142.50 USD status=approved latency=87ms", {"transaction.id": "TXN-88421", "transaction.amount": "142.50", "transaction.currency": "USD"}),
        ("WARN",  "Connection pool pressure: 78/100 connections active, 4 waiting", {"db.pool.active": "78", "db.pool.max": "100", "db.pool.waiting": "4"}),
        ("ERROR", "SLO breach: p95_latency=847ms exceeds 500ms threshold", {"slo.metric": "p95_latency", "slo.current": "847", "slo.threshold": "500"}),
        ("INFO",  "Transaction processed: txn_id=TXN-88422 amount=2100.00 USD status=approved latency=54ms", {"transaction.id": "TXN-88422", "transaction.amount": "2100.00", "transaction.currency": "USD"}),
        ("WARN",  "Upstream slow response: data-ingestion 1240ms (SLO: 500ms)", {"upstream.service": "data-ingestion", "upstream.latency_ms": "1240"}),
        ("ERROR", "Database connection pool timeout: all 50 connections in use", {"db.pool.active": "50", "db.pool.max": "50", "db.pool.timeout": "true"}),
        ("INFO",  "Batch settlement completed: 342 transactions, total=842,100.00 USD", {"settlement.count": "342", "settlement.total": "842100.00"}),
    ],
    "inventory-service": [
        ("INFO",  "Inventory check: sku=EXX-CRUDE-PIPE-4IN qty_available=1450 facility=Houston", {"inventory.sku": "EXX-CRUDE-PIPE-4IN", "inventory.qty": "1450", "facility": "Houston"}),
        ("WARN",  "Low stock alert: sku=EXX-VALVE-GATE-6IN qty=12 reorder_point=50 facility=Midland", {"inventory.sku": "EXX-VALVE-GATE-6IN", "inventory.qty": "12", "reorder.point": "50"}),
        ("INFO",  "Audit log written: item=EXX-PUMP-CENTRIFUGAL delta=-5 operator=jsmith@exxon.com", {"inventory.operator": "jsmith@exxon.com", "audit.action": "inventory_update"}),
        ("ERROR", "Cannot write to Splunk HEC: 503 Service Unavailable — falling back to OTLP", {"splunk.hec.status": "503", "fallback": "otlp"}),
        ("WARN",  "Compliance audit gap: 30-minute log window missing for inventory-service (Splunk forwarder failure)", {"audit.gap_minutes": "30", "forwarder": "splunk"}),
        ("INFO",  "Inventory sync complete: 12,450 items reconciled across Houston, Midland, Corpus Christi", {"sync.item_count": "12450", "sync.sites": "Houston,Midland,CorpusChristi"}),
    ],
    "openshift-operator": [
        ("INFO",  "Pod scale-up: api-gateway replica count 3→5 (CPU utilization 78%)", {"k8s.deployment.name": "api-gateway", "k8s.replica.old": "3", "k8s.replica.new": "5"}),
        ("WARN",  "Node memory pressure: openshift-worker-02 available=1.2Gi requests=14.8Gi", {"k8s.node.name": "openshift-worker-02", "k8s.memory.available": "1.2Gi"}),
        ("INFO",  "Rolling update complete: payment-processor v2.3.1→v2.3.2 (0 errors)", {"k8s.deployment.name": "payment-processor", "k8s.rollout.version": "v2.3.2"}),
        ("ERROR", "CrashLoopBackOff: openshift-operator pod openshift-operator-7c8b9-xqr2t (exit 137 OOMKilled)", {"k8s.pod.name": "openshift-operator-7c8b9-xqr2t", "k8s.exit_code": "137"}),
        ("WARN",  "PodDisruptionBudget violation risk: min_available=2 ready=2 disruptions_allowed=0", {"k8s.pdb.min_available": "2", "k8s.pdb.ready": "2"}),
    ],
    "network-monitor": [
        ("WARN",  "SNMP linkDown: cisco-sw-houston-01 GigabitEthernet0/47 ifOperStatus=down", {"device.hostname": "cisco-sw-houston-01", "network.interface": "GigabitEthernet0/47", "snmp.trap.type": "linkDown"}),
        ("INFO",  "SNMP linkUp: cisco-sw-houston-01 GigabitEthernet0/47 recovered after 12s", {"device.hostname": "cisco-sw-houston-01", "network.interface": "GigabitEthernet0/47", "snmp.trap.type": "linkUp"}),
        ("WARN",  "ThousandEyes jitter alert: TE-MID-001 jitter=47.2ms threshold=20ms Midland-MPLS-to-Azure", {"thousandeyes.agent": "TE-MID-001", "network.jitter_ms": "47.2", "network.site": "Midland-Field-Ops"}),
        ("ERROR", "Circuit flap detected: cisco-sw-houston-01 (3 state changes in 5 min)", {"device.hostname": "cisco-sw-houston-01", "network.flap_count": "3", "network.site": "Houston-Refinery-Campus"}),
        ("INFO",  "CMDB enrichment applied: cisco-sw-midland-03 owner=exxon-infra-team site=Midland-Field-Ops", {"device.hostname": "cisco-sw-midland-03", "network.site": "Midland-Field-Ops"}),
    ],
    "avd-broker": [
        ("INFO",  "AVD session established: jsmith@exxon.com avd-mid-w10-042 pool=avd-mid-pool logon=4200ms", {"user.name": "jsmith@exxon.com", "host.name": "avd-mid-w10-042", "avd.logon_ms": "4200"}),
        ("WARN",  "Slow logon: tmorales@exxon.com avd-mid-w10-043 logon=29100ms SLO=5000ms", {"user.name": "tmorales@exxon.com", "host.name": "avd-mid-w10-043", "avd.logon_ms": "29100"}),
        ("ERROR", "Session reconnect storm: 14 users, 47 reconnects in 90s from Midland site", {"avd.reconnect_count": "47", "avd.affected_users": "14", "network.site": "Midland-Field-Ops"}),
        ("ERROR", "Profile load failure: jsmith@exxon.com FSLogix container mount timeout 30s", {"user.name": "jsmith@exxon.com", "avd.fslogix.error": "VHD mount timeout"}),
        ("INFO",  "Pool health: avd-mid-pool 18/20 sessions active, 2 degraded", {"avd.pool": "avd-mid-pool", "avd.sessions.active": "18", "avd.sessions.degraded": "2"}),
    ],
}

_SEVERITY_WEIGHTS = {
    "INFO": 65,
    "WARN": 25,
    "ERROR": 10,
}
_SEVERITY_LIST: list[str] = []
for _sev, _weight in _SEVERITY_WEIGHTS.items():
    _SEVERITY_LIST.extend([_sev] * _weight)


def _build_resource(service_name: str, ns: str, svc_config: dict) -> dict:
    """Build OTLP resource WITHOUT data_stream.* so logs land in logs.otel."""
    return {
        "attributes": _format_attributes({
            "service.name": service_name,
            "service.namespace": ns,
            "service.version": "2.0.0",
            "service.instance.id": f"{service_name}-001",
            "telemetry.sdk.language": svc_config.get("language", "python"),
            "telemetry.sdk.name": "opentelemetry",
            "telemetry.sdk.version": "1.24.0",
            "cloud.provider": svc_config.get("cloud_provider", "azure"),
            "cloud.platform": svc_config.get("cloud_platform", "azure_app_service"),
            "cloud.region": svc_config.get("cloud_region", "southcentralus"),
            "cloud.availability_zone": svc_config.get("cloud_availability_zone", "southcentralus-1"),
            "deployment.environment": f"production-{ns}",
            # No data_stream.* → routes to logs.otel on Elastic Serverless
        }),
        "schemaUrl": SCHEMA_URL,
    }


def run(client: OTLPClient, stop_event: threading.Event,
        scenario_data: dict | None = None) -> None:
    """Emit structured application logs from Exxon services into logs.otel."""
    rng = random.Random()

    ns = NAMESPACE
    services: dict = {}

    if scenario_data:
        ns = scenario_data.get("namespace", NAMESPACE)
        raw_services = scenario_data.get("services", {})
        # Only use services that have templates
        services = {k: v for k, v in raw_services.items() if k in _SERVICE_LOGS}

    if not services:
        # Fallback defaults matching the Exxon scenario
        services = {
            "api-gateway":        {"cloud_provider": "azure", "cloud_platform": "azure_app_service", "cloud_region": "southcentralus", "cloud_availability_zone": "southcentralus-1", "language": "java"},
            "payment-processor":  {"cloud_provider": "azure", "cloud_platform": "azure_app_service", "cloud_region": "southcentralus", "cloud_availability_zone": "southcentralus-2", "language": "dotnet"},
            "inventory-service":  {"cloud_provider": "azure", "cloud_platform": "azure_app_service", "cloud_region": "southcentralus", "cloud_availability_zone": "southcentralus-3", "language": "python"},
            "openshift-operator": {"cloud_provider": "azure", "cloud_platform": "azure_aks",         "cloud_region": "southcentralus", "cloud_availability_zone": "southcentralus-1", "language": "go"},
            "network-monitor":    {"cloud_provider": "azure", "cloud_platform": "azure_vm",          "cloud_region": "southcentralus", "cloud_availability_zone": "southcentralus-2", "language": "python"},
            "avd-broker":         {"cloud_provider": "azure", "cloud_platform": "azure_vm",          "cloud_region": "southcentralus", "cloud_availability_zone": "southcentralus-1", "language": "dotnet"},
        }

    # Pre-build resources (keyed by service name)
    resources = {svc: _build_resource(svc, ns, cfg) for svc, cfg in services.items()}

    total_sent = 0
    logger.info("App log generator started — %d Exxon services → logs.otel", len(services))

    while not stop_event.is_set():
        batch_size = rng.randint(BATCH_SIZE_MIN, BATCH_SIZE_MAX)

        # Pick a random service and emit a batch of logs for it
        service_name = rng.choice(list(services.keys()))
        resource = resources[service_name]
        templates = _SERVICE_LOGS.get(service_name, [])
        if not templates:
            stop_event.wait(rng.uniform(BATCH_INTERVAL_MIN, BATCH_INTERVAL_MAX))
            continue

        records = []
        for _ in range(batch_size):
            severity, body, extra_attrs = rng.choice(templates)
            trace_id = secrets.token_hex(16)
            span_id = secrets.token_hex(8)

            attrs = {
                "event.domain": "exxon-infrastructure",
                "event.kind": "event",
                **extra_attrs,
            }

            records.append(
                client.build_log_record(
                    severity=severity,
                    body=body,
                    attributes=attrs,
                    trace_id=trace_id,
                    span_id=span_id,
                )
            )

        client.send_logs(resource, records)
        total_sent += len(records)
        logger.debug("App logs: sent %d records for %s (total=%d)", len(records), service_name, total_sent)

        stop_event.wait(rng.uniform(BATCH_INTERVAL_MIN, BATCH_INTERVAL_MAX))

    logger.info("App log generator stopped. Total: %d log records", total_sent)


def main() -> None:
    import os
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    client = OTLPClient()
    stop_event = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop_event.set())
    signal.signal(signal.SIGTERM, lambda *_: stop_event.set())
    duration = int(os.environ.get("RUN_DURATION", "60"))
    t = threading.Timer(duration, stop_event.set)
    t.daemon = True
    t.start()
    logger.info("Running standalone for %ds", duration)
    run(client, stop_event)
    t.cancel()
    client.close()


if __name__ == "__main__":
    main()
