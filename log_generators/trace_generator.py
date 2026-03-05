#!/usr/bin/env python3
"""Trace Generator — sends distributed traces for APM Service Map via OTLP.

Generates realistic distributed traces across the active scenario's services with proper
parent-child span relationships, service topology, and APM-compatible attributes.

Usage (standalone):
    python3 -m log_generators.trace_generator
"""

from __future__ import annotations

import logging
import os
import random
import secrets
import signal
import threading
import time

from app.telemetry import OTLPClient, _format_attributes, SCHEMA_URL
from app.config import SERVICES, CHANNEL_REGISTRY, ACTIVE_SCENARIO, NAMESPACE
from app.trace_context import _trace_context_store

logger = logging.getLogger("trace-generator")

# ── Configuration ─────────────────────────────────────────────────────────────
BATCH_INTERVAL_MIN = 2
BATCH_INTERVAL_MAX = 4

# Span kind constants
SPAN_KIND_INTERNAL = 1
SPAN_KIND_SERVER = 2
SPAN_KIND_CLIENT = 3

# Status codes
STATUS_OK = 1
STATUS_ERROR = 2


def _load_topology():
    """Load topology data from the active scenario."""
    from scenarios import get_scenario
    scenario = get_scenario(ACTIVE_SCENARIO)
    return scenario.service_topology, scenario.entry_endpoints, scenario.db_operations


# ── Module-level topology (loaded once) ──────────────────────────────────────
SERVICE_TOPOLOGY, ENTRY_ENDPOINTS, DB_OPERATIONS = _load_topology()


# ── Helpers ───────────────────────────────────────────────────────────────────
def _gen_trace_id() -> str:
    return secrets.token_hex(16)


def _gen_span_id() -> str:
    return secrets.token_hex(8)


def _build_resource(service_name: str, services: dict | None = None, namespace: str | None = None) -> dict:
    _services = services or SERVICES
    _namespace = namespace or NAMESPACE
    cfg = _services[service_name]
    language = cfg.get("language", "python")
    attrs = {
        "service.name": service_name,
        "service.namespace": _namespace,
        "service.version": "1.0.0",
        "service.instance.id": f"{service_name}-001",
        "telemetry.sdk.language": language,
        "telemetry.sdk.name": "opentelemetry",
        "telemetry.sdk.version": "1.24.0",
        "cloud.provider": cfg["cloud_provider"],
        "cloud.platform": cfg["cloud_platform"],
        "cloud.region": cfg["cloud_region"],
        "cloud.availability_zone": cfg["cloud_availability_zone"],
        "deployment.environment": f"production-{_namespace}",
        "host.name": f"{service_name}-host",
        "host.architecture": "amd64",
        "os.type": "linux",
        "data_stream.type": "traces",
        "data_stream.dataset": "generic",
        "data_stream.namespace": "default",
    }
    # Add process.runtime attributes so Elastic APM can identify the runtime
    _RUNTIME_ATTRS = {
        "java": {
            "process.runtime.name": "OpenJDK Runtime Environment",
            "process.runtime.version": "21.0.5+11-LTS",
            "process.runtime.description": "Eclipse Adoptium OpenJDK 64-Bit Server VM 21.0.5+11-LTS",
        },
        "python": {
            "process.runtime.name": "CPython",
            "process.runtime.version": "3.12.3",
            "process.runtime.description": "CPython 3.12.3",
        },
        "go": {
            "process.runtime.name": "go",
            "process.runtime.version": "go1.22.4",
            "process.runtime.description": "go1.22.4 linux/amd64",
        },
        "dotnet": {
            "process.runtime.name": ".NET",
            "process.runtime.version": "8.0.6",
            "process.runtime.description": ".NET 8.0.6",
        },
        "rust": {
            "process.runtime.name": "rustc",
            "process.runtime.version": "1.79.0",
            "process.runtime.description": "rustc 1.79.0",
        },
        "cpp": {
            "process.runtime.name": "gcc",
            "process.runtime.version": "13.2.0",
            "process.runtime.description": "GCC 13.2.0",
        },
    }
    if language in _RUNTIME_ATTRS:
        attrs.update(_RUNTIME_ATTRS[language])
    return {
        "attributes": _format_attributes(attrs),
        "schemaUrl": SCHEMA_URL,
    }


def _generate_trace(client: OTLPClient, resources: dict, rng: random.Random,
                    chaos_affected: set[str] | None = None,
                    *, services: dict | None = None, namespace: str | None = None,
                    service_topology: dict | None = None,
                    entry_endpoints: dict | None = None,
                    db_operations: dict | None = None,
                    latency_multiplier: float = 1.0,
                    scenario=None,
                    active_channels: list[int] | None = None,
                    channel_registry: dict | None = None) -> dict[str, list]:
    """Generate a single distributed trace across multiple services.

    Returns a dict mapping service_name -> list of spans for that service.
    When chaos_affected is provided, those services get high error rates (70%)
    and elevated latency; all others use a healthy 3% baseline.
    """
    _services = services or SERVICES
    _namespace = namespace or NAMESPACE
    _topology = service_topology or SERVICE_TOPOLOGY
    _endpoints = entry_endpoints or ENTRY_ENDPOINTS
    _db_ops = db_operations or DB_OPERATIONS

    trace_id = _gen_trace_id()
    spans_by_service: dict[str, list] = {}

    # Pick a random entry-point service (weighted toward first service)
    service_names = list(_services.keys())
    first_service = service_names[0]
    entry_services = [first_service] * 4 + [
        s for s in service_names[1:] if s in _endpoints
    ]
    entry_service = rng.choice(entry_services)
    entry_endpoint, entry_method = rng.choice(_endpoints[entry_service])

    # Determine if this trace has errors — chaos-aware probability
    if chaos_affected and entry_service in chaos_affected:
        is_error_trace = rng.random() < 0.70
    else:
        is_error_trace = rng.random() < 0.03

    error_service = None
    if is_error_trace:
        # If entry service is affected by chaos, it is the error source
        if chaos_affected and entry_service in chaos_affected:
            error_service = entry_service
        else:
            downstream = _topology.get(entry_service, [])
            if downstream:
                error_service = rng.choice(downstream)[0]

    # Latency: affected services get 200-2000ms, normal get 50-500ms
    if chaos_affected and entry_service in chaos_affected:
        total_duration = rng.randint(200, 2000)
    else:
        total_duration = rng.randint(50, 500)
    # Apply latency multiplier from infra spikes
    total_duration = int(total_duration * latency_multiplier)

    # Build per-service -> channel mapping for RCA clues
    _svc_channels: dict[str, list[int]] = {}
    if active_channels and channel_registry:
        for ch_id in active_channels:
            ch = channel_registry.get(ch_id, {})
            for svc in ch.get("affected_services", []) + ch.get("cascade_services", []):
                _svc_channels.setdefault(svc, []).append(ch_id)

    # Root SERVER span for the entry-point service
    root_span_id = _gen_span_id()
    root_status = STATUS_ERROR if (is_error_trace and error_service == entry_service) else STATUS_OK
    root_http_status = rng.choice([500, 502, 503]) if root_status == STATUS_ERROR else 200

    # Helper: build extra scenario attrs for a span
    def _extra_attrs(svc: str, is_err: bool) -> dict:
        extra = {}
        if scenario:
            extra.update(scenario.get_trace_attributes(svc, rng))
            if _svc_channels.get(svc):
                for ch in _svc_channels[svc]:
                    extra.update(scenario.get_rca_clues(ch, svc, rng))
            if active_channels:
                # Use high probability (90%) for both errors AND affected services
                # (affected services have elevated latency, so attribute must
                # correlate with slow traces too, not just failed ones)
                is_affected = bool(_svc_channels.get(svc))
                for ch in active_channels:
                    extra.update(scenario.get_correlation_attribute(ch, is_err or is_affected, rng))
        return extra

    root_attrs = {
        "http.request.method": entry_method,
        "url.path": entry_endpoint,
        "http.response.status_code": root_http_status,
        "server.address": f"{entry_service}-host",
        "server.port": 8080,
        "network.protocol.version": "1.1",
    }
    root_attrs.update(_extra_attrs(entry_service, root_status == STATUS_ERROR))

    root_span = client.build_span(
        name=f"{entry_method} {entry_endpoint}",
        trace_id=trace_id,
        span_id=root_span_id,
        kind=SPAN_KIND_SERVER,
        duration_ms=total_duration,
        status_code=root_status,
        attributes=root_attrs,
    )
    spans_by_service.setdefault(entry_service, []).append(root_span)

    # Add DB span if this service does DB operations
    if entry_service in _db_ops and rng.random() < 0.6:
        op, table, statement = rng.choice(_db_ops[entry_service])
        db_span_id = _gen_span_id()
        db_duration = rng.randint(2, min(30, total_duration // 3))
        db_span = client.build_span(
            name=f"{op} {table}",
            trace_id=trace_id,
            span_id=db_span_id,
            parent_span_id=root_span_id,
            kind=SPAN_KIND_CLIENT,
            duration_ms=db_duration,
            status_code=STATUS_OK,
            attributes={
                "db.system": "mysql",
                "db.name": f"{_namespace}_telemetry",
                "db.statement": statement,
                "db.operation": op,
                "db.sql.table": table,
                "net.peer.name": f"{_namespace}-mysql-host",
                "net.peer.port": 3306,
            },
        )
        spans_by_service.setdefault(entry_service, []).append(db_span)

    # Generate downstream CLIENT+SERVER spans based on topology
    downstream_calls = _topology.get(entry_service, [])
    if downstream_calls:
        # Pick 1-3 downstream calls
        num_calls = min(len(downstream_calls), rng.randint(1, 3))
        selected_calls = rng.sample(downstream_calls, num_calls)

        for callee_service, callee_endpoint, callee_method in selected_calls:
            # Chaos-aware: affected callee services get elevated latency + error chance
            if chaos_affected and callee_service in chaos_affected:
                call_duration = rng.randint(100, max(200, total_duration // 2))
                callee_error = rng.random() < 0.70
            else:
                call_duration = rng.randint(10, max(20, total_duration // 2))
                callee_error = False

            is_this_error = (is_error_trace and callee_service == error_service) or callee_error
            call_status = STATUS_ERROR if is_this_error else STATUS_OK
            call_http_status = rng.choice([500, 502, 503, 504]) if is_this_error else 200

            # CLIENT span on the caller side
            client_span_id = _gen_span_id()
            client_span = client.build_span(
                name=f"{callee_method} {callee_endpoint}",
                trace_id=trace_id,
                span_id=client_span_id,
                parent_span_id=root_span_id,
                kind=SPAN_KIND_CLIENT,
                duration_ms=call_duration,
                status_code=call_status,
                attributes={
                    "http.request.method": callee_method,
                    "url.path": callee_endpoint,
                    "http.response.status_code": call_http_status,
                    "server.address": f"{callee_service}-host",
                    "server.port": 8080,
                    "net.peer.name": f"{callee_service}-host",
                    "net.peer.port": 8080,
                },
            )
            spans_by_service.setdefault(entry_service, []).append(client_span)

            # SERVER span on the callee side
            server_span_id = _gen_span_id()
            server_duration = call_duration - rng.randint(1, max(1, call_duration // 5))
            callee_attrs = {
                "http.request.method": callee_method,
                "url.path": callee_endpoint,
                "http.response.status_code": call_http_status,
                "server.address": f"{callee_service}-host",
                "server.port": 8080,
            }
            callee_attrs.update(_extra_attrs(callee_service, is_this_error))
            server_span = client.build_span(
                name=f"{callee_method} {callee_endpoint}",
                trace_id=trace_id,
                span_id=server_span_id,
                parent_span_id=client_span_id,
                kind=SPAN_KIND_SERVER,
                duration_ms=max(1, server_duration),
                status_code=call_status,
                attributes=callee_attrs,
            )
            spans_by_service.setdefault(callee_service, []).append(server_span)

            # DB span on the callee side (if applicable)
            if callee_service in _db_ops and rng.random() < 0.5:
                op, table, statement = rng.choice(_db_ops[callee_service])
                db_span_id = _gen_span_id()
                db_duration = rng.randint(1, max(1, server_duration // 3))
                db_span = client.build_span(
                    name=f"{op} {table}",
                    trace_id=trace_id,
                    span_id=db_span_id,
                    parent_span_id=server_span_id,
                    kind=SPAN_KIND_CLIENT,
                    duration_ms=db_duration,
                    status_code=STATUS_OK,
                    attributes={
                        "db.system": "mysql",
                        "db.name": f"{_namespace}_telemetry",
                        "db.statement": statement,
                        "db.operation": op,
                        "db.sql.table": table,
                        "net.peer.name": f"{_namespace}-mysql-host",
                        "net.peer.port": 3306,
                    },
                )
                spans_by_service.setdefault(callee_service, []).append(db_span)

            # Second-level downstream calls (e.g., navigation -> sensor-validator)
            second_downstream = _topology.get(callee_service, [])
            if second_downstream and rng.random() < 0.4:
                second_callee, second_endpoint, second_method = rng.choice(second_downstream)
                second_duration = rng.randint(5, max(5, server_duration // 2))
                second_status = STATUS_OK

                # CLIENT span
                second_client_id = _gen_span_id()
                second_client_span = client.build_span(
                    name=f"{second_method} {second_endpoint}",
                    trace_id=trace_id,
                    span_id=second_client_id,
                    parent_span_id=server_span_id,
                    kind=SPAN_KIND_CLIENT,
                    duration_ms=second_duration,
                    status_code=second_status,
                    attributes={
                        "http.request.method": second_method,
                        "url.path": second_endpoint,
                        "http.response.status_code": 200,
                        "server.address": f"{second_callee}-host",
                        "server.port": 8080,
                        "net.peer.name": f"{second_callee}-host",
                        "net.peer.port": 8080,
                    },
                )
                spans_by_service.setdefault(callee_service, []).append(second_client_span)

                # SERVER span
                second_server_id = _gen_span_id()
                second_server_span = client.build_span(
                    name=f"{second_method} {second_endpoint}",
                    trace_id=trace_id,
                    span_id=second_server_id,
                    parent_span_id=second_client_id,
                    kind=SPAN_KIND_SERVER,
                    duration_ms=max(1, second_duration - 2),
                    status_code=second_status,
                    attributes={
                        "http.request.method": second_method,
                        "url.path": second_endpoint,
                        "http.response.status_code": 200,
                        "server.address": f"{second_callee}-host",
                        "server.port": 8080,
                    },
                )
                spans_by_service.setdefault(second_callee, []).append(second_server_span)

    return spans_by_service


# ── Run loop (used by ServiceManager and standalone) ──────────────────────────
def run(client: OTLPClient, stop_event: threading.Event, chaos_controller=None,
        scenario_data: dict | None = None) -> None:
    """Run trace generator loop until stop_event is set."""
    rng = random.Random()

    # Use scenario_data overrides or fall back to module-level globals
    _all_services = scenario_data["services"] if scenario_data else SERVICES
    _namespace = scenario_data["namespace"] if scenario_data else NAMESPACE
    _channel_registry = scenario_data["channel_registry"] if scenario_data else CHANNEL_REGISTRY
    _all_topology = scenario_data["service_topology"] if scenario_data else SERVICE_TOPOLOGY
    _all_endpoints = scenario_data["entry_endpoints"] if scenario_data else ENTRY_ENDPOINTS
    _db_ops = scenario_data["db_operations"] if scenario_data else DB_OPERATIONS
    _scenario = scenario_data.get("scenario") if scenario_data else None

    # Filter out services that don't generate traces (e.g. infrastructure/network devices)
    excluded = {name for name, cfg in _all_services.items() if cfg.get("generates_traces") is False}
    _services = {name: cfg for name, cfg in _all_services.items() if name not in excluded}
    _topology = {
        caller: [(callee, ep, method) for callee, ep, method in calls if callee not in excluded]
        for caller, calls in _all_topology.items() if caller not in excluded
    }
    _endpoints = {name: eps for name, eps in _all_endpoints.items() if name not in excluded}

    if excluded:
        logger.info("Excluding %d infra services from traces: %s", len(excluded), ", ".join(sorted(excluded)))

    resources = {svc: _build_resource(svc, services=_services, namespace=_namespace) for svc in _services}
    total_traces = 0
    total_spans = 0

    logger.info("Trace generator started (chaos_aware=%s)", chaos_controller is not None)

    while not stop_event.is_set():
        # Build set of services affected by active chaos channels
        chaos_affected: set[str] = set()
        _active_channels: list[int] = []
        if chaos_controller:
            _active_channels = chaos_controller.get_active_channels()
            for ch_id in _active_channels:
                ch = _channel_registry.get(ch_id)
                if ch:
                    chaos_affected.update(ch["affected_services"])

        # Read latency multiplier from infra spikes
        _latency_mult = 1.0
        if chaos_controller:
            _spikes = chaos_controller.get_infra_spikes()
            _latency_mult = _spikes.get("latency_multiplier", 1.0)

        num_traces = rng.randint(2, 5)

        batch_by_service: dict[str, list] = {}
        for _ in range(num_traces):
            trace_spans = _generate_trace(
                client, resources, rng, chaos_affected or None,
                services=_services, namespace=_namespace,
                service_topology=_topology, entry_endpoints=_endpoints,
                db_operations=_db_ops,
                latency_multiplier=_latency_mult,
                scenario=_scenario,
                active_channels=_active_channels or None,
                channel_registry=_channel_registry,
            )
            for svc, spans in trace_spans.items():
                batch_by_service.setdefault(svc, []).extend(spans)
                # Publish latest trace context for log-trace correlation
                if spans:
                    _trace_context_store.set(svc, spans[0]["traceId"], spans[0]["spanId"])

        batch_span_count = 0
        for svc, spans in batch_by_service.items():
            if spans:
                client.send_traces(resources[svc], spans)
                batch_span_count += len(spans)

        total_traces += num_traces
        total_spans += batch_span_count
        logger.info(
            "Sent %d traces (%d spans) — total: %d traces, %d spans",
            num_traces, batch_span_count, total_traces, total_spans,
        )

        sleep_time = rng.uniform(BATCH_INTERVAL_MIN, BATCH_INTERVAL_MAX)
        stop_event.wait(sleep_time)

    logger.info("Trace generator stopped. Total: %d traces, %d spans", total_traces, total_spans)


# ── Standalone entry point ────────────────────────────────────────────────────
def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    client = OTLPClient()
    stop_event = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop_event.set())
    signal.signal(signal.SIGTERM, lambda *_: stop_event.set())

    duration = int(os.environ.get("RUN_DURATION", "60"))
    timer = threading.Timer(duration, stop_event.set)
    timer.daemon = True
    timer.start()
    logger.info("Running for %ds (standalone mode)", duration)

    run(client, stop_event)
    timer.cancel()
    client.close()


if __name__ == "__main__":
    main()
