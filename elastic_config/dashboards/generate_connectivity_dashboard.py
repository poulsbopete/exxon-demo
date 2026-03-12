#!/usr/bin/env python3
"""
Generate a Client Connectivity E2E dashboard NDJSON for Kibana.

Modelled after the Exxon "Client Connectivity E2E — Command Center" dashboard
shown in the demo. Shows reliability % and health for:
  - Connectivity: WAN, LAN, Core Internet (SNMP + network-monitor logs)
  - Zero Trust: AppGate, iboss (fault-events-exxon)
  - Application Services: api-gateway, payment-processor, inventory-service, avd-broker
  - Authentication: azure-ad-proxy (fault_error_type auth_failure_storm)
  - Core Service Details: error table across all services

Reliability % = (1 - error_logs / total_logs) × 100
Health        = green when reliability ≥ 99%, amber 95–99%, red < 95%

Usage (standalone):
    python3 elastic_config/dashboards/generate_connectivity_dashboard.py
"""

import json
import os
import uuid

# ── Helpers reused from exec dashboard ────────────────────────────────────────

def uid():
    return str(uuid.uuid4())


def make_ref(data_view_id, layer_id):
    return {
        "id": data_view_id,
        "name": f"indexpattern-datasource-layer-{layer_id}",
        "type": "index-pattern",
    }


def make_layer(layer_id, column_order, columns, index_pattern_id=None):
    layer = {
        "columnOrder": column_order,
        "columns": columns,
        "ignoreGlobalFilters": False,
        "incompleteColumns": {},
        "sampling": 1,
    }
    if index_pattern_id:
        layer["indexPatternId"] = index_pattern_id
    return {layer_id: layer}


def make_state(layers_dict, visualization, query="", filters=None):
    return {
        "adHocDataViews": {},
        "datasourceStates": {
            "formBased": {"layers": layers_dict},
            "indexpattern": {"layers": {}},
            "textBased": {"layers": {}},
        },
        "filters": filters or [],
        "internalReferences": [],
        "query": {"language": "kuery", "query": query},
        "visualization": visualization,
    }


def make_panel(panel_id, grid, title, vis_type, state, references):
    return {
        "embeddableConfig": {
            "attributes": {
                "references": references,
                "state": state,
                "title": title,
                "type": "lens",
                "visualizationType": vis_type,
                "version": 2,
            },
            "enhancements": {"dynamicActions": {"events": []}},
            "hidePanelTitles": False,
            "syncColors": False,
            "syncCursor": True,
            "syncTooltips": False,
        },
        "gridData": grid,
        "panelIndex": panel_id,
        "type": "lens",
    }


def col_count(label="Count", kql_filter=None):
    col = {
        "customLabel": True,
        "dataType": "number",
        "isBucketed": False,
        "label": label,
        "operationType": "count",
        "params": {"emptyAsNull": True},
        "scale": "ratio",
        "sourceField": "___records___",
    }
    if kql_filter:
        col["filter"] = {"language": "kuery", "query": kql_filter}
    return col


def col_formula(formula, label):
    return {
        "customLabel": True,
        "dataType": "number",
        "isBucketed": False,
        "label": label,
        "operationType": "formula",
        "params": {"formula": formula, "isFormulaBroken": False},
        "scale": "ratio",
    }


def col_date_histogram(interval="1m"):
    return {
        "customLabel": True,
        "dataType": "date",
        "isBucketed": True,
        "label": "@timestamp",
        "operationType": "date_histogram",
        "params": {"interval": interval},
        "scale": "interval",
        "sourceField": "@timestamp",
    }


def col_terms(source_field, label, size=10):
    return {
        "customLabel": True,
        "dataType": "string",
        "isBucketed": True,
        "label": label,
        "operationType": "terms",
        "params": {
            "size": size,
            "orderDirection": "desc",
            "orderBy": {"type": "alphabetical"},
            "missingBucket": False,
            "otherBucket": False,
        },
        "scale": "ordinal",
        "sourceField": source_field,
    }


# ── Palette: Green when HIGH (reliability), Red when LOW ─────────────────────
PALETTE_RELIABILITY = {
    "name": "custom",
    "type": "palette",
    "params": {
        "steps": 3,
        "name": "custom",
        "reverse": False,
        "rangeType": "number",
        "rangeMin": 0,
        "rangeMax": 100,
        "progression": "fixed",
        "stops": [
            {"color": "#E7664C", "stop": 95},    # red:   0–95%
            {"color": "#D6BF57", "stop": 99},    # amber: 95–99%
            {"color": "#54B399", "stop": 100},   # green: 99–100%
        ],
        "colorStops": [
            {"color": "#E7664C", "stop": 0},
            {"color": "#D6BF57", "stop": 95},
            {"color": "#54B399", "stop": 99},
        ],
        "continuity": "above",
        "maxSteps": 5,
    },
}

PALETTE_ERRORS = {
    "name": "custom",
    "type": "palette",
    "params": {
        "steps": 3,
        "name": "custom",
        "reverse": False,
        "rangeType": "number",
        "rangeMin": 0,
        "rangeMax": None,
        "progression": "fixed",
        "stops": [
            {"color": "#54B399", "stop": 2},
            {"color": "#D6BF57", "stop": 10},
            {"color": "#E7664C", "stop": 9999},
        ],
        "colorStops": [
            {"color": "#54B399", "stop": 0},
            {"color": "#D6BF57", "stop": 2},
            {"color": "#E7664C", "stop": 10},
        ],
        "continuity": "above",
        "maxSteps": 5,
    },
}

# ── Reliability tile builder ──────────────────────────────────────────────────

LOGS_INDEX = "logs*"
FAULT_INDEX = "fault-events-exxon"


def _reliability_tile(panel_id, grid, title, subtitle, kql_scope="", index=LOGS_INDEX):
    """
    Metric tile showing reliability % = (1 - errors/total) * 100.
    kql_scope: optional KQL to scope to a specific service (added to filter).
    """
    lid = uid()
    cid = uid()

    formula = (
        "(1 - count(kql='severity_text: \"ERROR\"') / count()) * 100"
        if not kql_scope else
        f"(1 - count(kql='severity_text: \"ERROR\" AND {kql_scope}') / count(kql='{kql_scope}')) * 100"
    )

    columns = {cid: col_formula(formula, f"{title} Reliability")}
    layer = make_layer(lid, [cid], columns, index)
    state = make_state(layer, {
        "layerId": lid,
        "layerType": "data",
        "metricAccessor": cid,
        "palette": PALETTE_RELIABILITY,
        "subtitle": subtitle,
    })
    return make_panel(panel_id, grid, title, "lnsMetric", state, [make_ref(index, lid)])


def _fault_reliability_tile(panel_id, grid, title, subtitle, fault_error_type):
    """
    Reliability tile for fault channels: green when no active faults.
    % = (1 - fault_events/total_events) * 100 scoped to error_type.
    """
    lid = uid()
    cid = uid()
    formula = f"(1 - count(kql='fault.error_type: \"{fault_error_type}\"') / (count() + 1)) * 100"
    columns = {cid: col_formula(formula, f"{title} Reliability")}
    layer = make_layer(lid, [cid], columns, FAULT_INDEX)
    state = make_state(layer, {
        "layerId": lid,
        "layerType": "data",
        "metricAccessor": cid,
        "palette": PALETTE_RELIABILITY,
        "subtitle": subtitle,
    })
    return make_panel(panel_id, grid, title, "lnsMetric", state, [make_ref(FAULT_INDEX, lid)])


def _error_count_tile(panel_id, grid, title, subtitle, kql_scope="", index=LOGS_INDEX):
    """Error count tile (for health row below reliability)."""
    lid = uid()
    cid = uid()
    filter_kql = 'severity_text: "ERROR"'
    if kql_scope:
        filter_kql = f'{filter_kql} AND {kql_scope}'
    columns = {cid: col_count("Errors", kql_filter=filter_kql)}
    layer = make_layer(lid, [cid], columns, index)
    state = make_state(layer, {
        "layerId": lid,
        "layerType": "data",
        "metricAccessor": cid,
        "palette": PALETTE_ERRORS,
        "subtitle": subtitle,
    })
    return make_panel(panel_id, grid, title, "lnsMetric", state, [make_ref(index, lid)])


def _markdown(panel_id, grid, content):
    return {
        "type": "DASHBOARD_MARKDOWN",
        "embeddableConfig": {"content": content},
        "panelIndex": panel_id,
        "gridData": grid,
    }


def _esql_table(panel_id, grid, title, esql_query, columns_def):
    """ES|QL datatable panel."""
    lid = uid()
    adhoc_id = uid()
    esql_state = {
        "adHocDataViews": {
            adhoc_id: {
                "allowHidden": False,
                "allowNoIndex": True,
                "fieldFormats": {},
                "id": adhoc_id,
                "name": "logs*",
                "runtimeFieldMap": {},
                "sourceFilters": [],
                "timeFieldName": "@timestamp",
                "title": "logs*",
                "type": "esql",
            }
        },
        "datasourceStates": {
            "textBased": {
                "layers": {
                    lid: {
                        "index": adhoc_id,
                        "query": {"esql": esql_query},
                        "columns": columns_def,
                        "timeField": "@timestamp",
                    }
                }
            },
        },
        "filters": [],
        "internalReferences": [
            {"id": adhoc_id, "name": f"textBasedLanguages-datasource-layer-{lid}", "type": "index-pattern"}
        ],
        "query": {"esql": esql_query},
        "visualization": {
            "layerId": lid,
            "layerType": "data",
            "columns": [{"columnId": c["columnId"]} for c in columns_def],
            "paging": {"enabled": True, "size": 10},
        },
    }
    return make_panel(panel_id, grid, title, "lnsDatatable", esql_state, [])


def _esql_col(field, es_type, col_type):
    return {
        "columnId": uid(),
        "fieldName": field,
        "label": field,
        "customLabel": False,
        "meta": {"esType": es_type, "type": col_type},
    }


# ── Line chart (errors over time by service) ──────────────────────────────────

def _error_timeseries(panel_id, grid, title, index=LOGS_INDEX, kql_filter=""):
    lid = uid()
    ts_cid = uid()
    svc_cid = uid()
    err_cid = uid()

    ts_col  = col_date_histogram("1m")
    ts_col["label"] = "@timestamp"

    svc_col = col_terms("service.name", "Service", size=8)
    err_col = col_count("Errors", kql_filter='severity_text: "ERROR"')

    columns = {ts_cid: ts_col, svc_cid: svc_col, err_cid: err_col}
    layer = make_layer(lid, [ts_cid, svc_cid, err_cid], columns, index)
    state = make_state(layer, {
        "axisTitlesVisibilitySettings": {"x": True, "yLeft": True, "yRight": True},
        "fittingFunction": "None",
        "gridlinesVisibilitySettings": {"x": True, "yLeft": True, "yRight": True},
        "labelsOrientation": {"x": 0, "yLeft": 0, "yRight": 0},
        "layers": [{
            "accessors": [err_cid],
            "layerId": lid,
            "layerType": "data",
            "seriesType": "line",
            "splitAccessor": svc_cid,
            "xAccessor": ts_cid,
        }],
        "legend": {"isVisible": True, "position": "right"},
        "preferredSeriesType": "line",
        "tickLabelsVisibilitySettings": {"x": True, "yLeft": True, "yRight": True},
        "valueLabels": "hide",
        "yTitle": "Errors/min",
    }, query=kql_filter)
    return make_panel(panel_id, grid, title, "lnsXY", state, [make_ref(index, lid)])


# ── Main generator ────────────────────────────────────────────────────────────

def generate_connectivity_dashboard_ndjson(scenario=None) -> str:
    """
    Returns NDJSON string for the Client Connectivity E2E dashboard.
    Works standalone (scenario=None) or within the deployer context.
    """
    ns = getattr(scenario, "namespace", "exxon") if scenario else "exxon"
    dashboard_id = f"{ns}-connectivity-dashboard"
    panels = []

    # ── Row 0 (y=0, h=2): Dashboard title ─────────────────────────────────────
    panels.append(_markdown("p_title", {"h": 2, "i": "p_title", "w": 48, "x": 0, "y": 0},
        "## 🔴 Core Services — Client Connectivity E2E"))

    # ── Row 1 — Section headers (y=2, h=2) ────────────────────────────────────
    panels.append(_markdown("p_h_conn",  {"h": 2, "i": "p_h_conn",  "w": 16, "x": 0,  "y": 2},
        "**Connectivity (Core Internet, WAN, LAN)**"))
    panels.append(_markdown("p_h_zt",    {"h": 2, "i": "p_h_zt",    "w": 16, "x": 16, "y": 2},
        "**Zero Trust (iboss, AppGate)**"))
    panels.append(_markdown("p_h_auth",  {"h": 2, "i": "p_h_auth",  "w": 16, "x": 32, "y": 2},
        "**Authentication (AD, Entra)**"))

    # ── Row 2 — Reliability tiles (y=4, h=7) ──────────────────────────────────
    # Connectivity: Core Internet = api-gateway, WAN = network-monitor (SNMP), LAN = SNMP
    panels.append(_reliability_tile("p_core_inet", {"h": 7, "i": "p_core_inet", "w": 6, "x": 0, "y": 4},
        "Core Internet", "Reliability",
        kql_scope='service.name: "api-gateway"'))
    panels.append(_reliability_tile("p_wan", {"h": 7, "i": "p_wan", "w": 5, "x": 6, "y": 4},
        "WAN", "Reliability",
        kql_scope='service.name: "network-monitor"'))
    panels.append(_reliability_tile("p_lan", {"h": 7, "i": "p_lan", "w": 5, "x": 11, "y": 4},
        "LAN", "Reliability",
        kql_scope='snmp.trap.type: *'))

    # Zero Trust: AppGate fault events, iboss fault events
    panels.append(_fault_reliability_tile("p_appgate", {"h": 7, "i": "p_appgate", "w": 8, "x": 16, "y": 4},
        "AppGate", "Zero Trust Reliability", "cert_expiry"))
    panels.append(_fault_reliability_tile("p_iboss",   {"h": 7, "i": "p_iboss",   "w": 8, "x": 24, "y": 4},
        "iboss", "Web Gateway Reliability", "policy_block"))

    # Authentication: azure-ad-proxy error rate
    panels.append(_reliability_tile("p_ad",    {"h": 7, "i": "p_ad",    "w": 8, "x": 32, "y": 4},
        "AD / Entra", "Auth Reliability",
        kql_scope='service.name: "azure-ad-proxy"'))
    panels.append(_error_count_tile("p_auth_err", {"h": 7, "i": "p_auth_err", "w": 8, "x": 40, "y": 4},
        "Auth Failures", "Event ID 4625 storm",
        kql_scope='service.name: "azure-ad-proxy"'))

    # ── Row 3 — Section header: Application Services (y=11, h=2) ──────────────
    panels.append(_markdown("p_h_app", {"h": 2, "i": "p_h_app", "w": 48, "x": 0, "y": 11},
        "**Application Services (Azure API + OpenShift)**"))

    # ── Row 4 — App service reliability tiles (y=13, h=7) ─────────────────────
    app_services = [
        ("p_apigw",   "api-gateway",         "API Gateway",        "Azure API Service"),
        ("p_payment", "payment-processor",   "Payment Processor",  "Azure API Service"),
        ("p_inv",     "inventory-service",   "Inventory Service",  "Azure API Service"),
        ("p_avd",     "avd-broker",          "AVD Broker",         "Azure Virtual Desktop"),
        ("p_oshift",  "openshift-operator",  "OpenShift Operator", "OCP K8s Platform"),
        ("p_netmon",  "network-monitor",     "Network Monitor",    "SNMP / WAN Agent"),
    ]
    tile_w = 8
    for i, (pid, svc, title, subtitle) in enumerate(app_services):
        panels.append(_reliability_tile(pid,
            {"h": 7, "i": pid, "w": tile_w, "x": i * tile_w, "y": 13},
            title, subtitle,
            kql_scope=f'service.name: "{svc}"'))

    # ── Row 5 — Error health (y=20, h=5) ──────────────────────────────────────
    for i, (pid, svc, title, subtitle) in enumerate(app_services):
        epid = f"{pid}_err"
        panels.append(_error_count_tile(epid,
            {"h": 5, "i": epid, "w": tile_w, "x": i * tile_w, "y": 20},
            f"{title} Health", f"Errors · {subtitle}",
            kql_scope=f'service.name: "{svc}"'))

    # ── Row 6 — Section header: Network & Security Events (y=25, h=2) ─────────
    panels.append(_markdown("p_h_net", {"h": 2, "i": "p_h_net", "w": 48, "x": 0, "y": 25},
        "**Network & Security Events**"))

    # ── Row 7 — Error time series + fault events bar (y=27, h=12) ─────────────
    panels.append(_error_timeseries("p_ts_errors",
        {"h": 12, "i": "p_ts_errors", "w": 28, "x": 0, "y": 27},
        "Error Rate by Service"))

    # Fault event counts by channel (bar)
    lid = uid(); ts_cid = uid(); ch_cid = uid(); cnt_cid = uid()
    ts_col  = col_date_histogram("1m")
    ch_col  = col_terms("fault.error_type", "Fault Type", size=12)
    cnt_col = col_count("Events")
    columns = {ts_cid: ts_col, ch_cid: ch_col, cnt_cid: cnt_col}
    layer = make_layer(lid, [ts_cid, ch_cid, cnt_cid], columns, FAULT_INDEX)
    state = make_state(layer, {
        "axisTitlesVisibilitySettings": {"x": True, "yLeft": True, "yRight": True},
        "fittingFunction": "None",
        "gridlinesVisibilitySettings": {"x": True, "yLeft": True, "yRight": True},
        "labelsOrientation": {"x": 0, "yLeft": 0, "yRight": 0},
        "layers": [{
            "accessors": [cnt_cid],
            "layerId": lid,
            "layerType": "data",
            "seriesType": "bar_stacked",
            "splitAccessor": ch_cid,
            "xAccessor": ts_cid,
        }],
        "legend": {"isVisible": True, "position": "right"},
        "preferredSeriesType": "bar_stacked",
        "tickLabelsVisibilitySettings": {"x": True, "yLeft": True, "yRight": True},
        "valueLabels": "hide",
        "yTitle": "Fault Events",
    })
    panels.append(make_panel("p_fault_bar",
        {"h": 12, "i": "p_fault_bar", "w": 20, "x": 28, "y": 27},
        "Active Fault Channels", "lnsXY", state, [make_ref(FAULT_INDEX, lid)]))

    # ── Row 8 — Section header: Core Service Details (y=39, h=2) ──────────────
    panels.append(_markdown("p_h_detail", {"h": 2, "i": "p_h_detail", "w": 48, "x": 0, "y": 39},
        "**Core Service Details**"))

    # ── Row 9 — Error detail table via ES|QL (y=41, h=14) ─────────────────────
    esql_detail = (
        "FROM logs* "
        "| WHERE @timestamp > NOW() - 1 hour AND severity_text == \"ERROR\" "
        "| STATS error_count = COUNT(*), last_error = MAX(@timestamp) BY service.name "
        "| SORT error_count DESC "
        "| LIMIT 20"
    )
    detail_cols = [
        _esql_col("service.name",  "keyword", "string"),
        _esql_col("error_count",   "long",    "number"),
        _esql_col("last_error",    "date",    "date"),
    ]
    panels.append(_esql_table("p_detail_tbl",
        {"h": 14, "i": "p_detail_tbl", "w": 28, "x": 0, "y": 41},
        "Service Error Summary (Last Hour)", esql_detail, detail_cols))

    # ── Fault detail table (y=41, w=20) ───────────────────────────────────────
    esql_fault = (
        "FROM fault-events-exxon "
        "| WHERE @timestamp > NOW() - 1 hour "
        "| STATS events = COUNT(*), services = VALUES(service.name) BY fault.error_type "
        "| SORT events DESC"
    )
    fault_cols = [
        _esql_col("fault.error_type", "keyword", "string"),
        _esql_col("events",           "long",    "number"),
        _esql_col("services",         "keyword", "string"),
    ]
    panels.append(_esql_table("p_fault_tbl",
        {"h": 14, "i": "p_fault_tbl", "w": 20, "x": 28, "y": 41},
        "Active Fault Events by Type", esql_fault, fault_cols))

    # ── Assemble dashboard saved object ───────────────────────────────────────
    dashboard_so = {
        "attributes": {
            "description": (
                "Client Connectivity E2E — Exxon Infrastructure 2.0. "
                "Reliability metrics for WAN, Zero Trust, Application Services, "
                "and Authentication. Powered by Elastic Serverless + OTLP."
            ),
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "filter": [],
                    "query": {"language": "kuery", "query": ""},
                })
            },
            "optionsJSON": json.dumps({
                "hidePanelTitles": False,
                "syncColors": True,
                "syncCursor": True,
                "syncTooltips": True,
                "useMargins": True,
            }),
            "panelsJSON": json.dumps(panels),
            "timeFrom": "now-1h",
            "timeTo": "now",
            "timeRestore": True,
            "title": "Client Connectivity E2E — Command Center",
            "version": 2,
        },
        "coreMigrationVersion": "8.8.0",
        "id": dashboard_id,
        "managed": False,
        "references": [],
        "type": "dashboard",
        "typeMigrationVersion": "10.2.0",
        "updated_at": "2026-03-12T00:00:00.000Z",
    }

    # ── Bundled data views (self-contained import) ─────────────────────────────
    data_views = [
        {"type": "index-pattern", "id": "logs*",              "attributes": {"title": "logs*",              "timeFieldName": "@timestamp"}, "references": [], "managed": False},
        {"type": "index-pattern", "id": "fault-events-exxon", "attributes": {"title": "fault-events-exxon", "timeFieldName": "@timestamp"}, "references": [], "managed": False},
    ]

    lines = [json.dumps(dv, separators=(",", ":")) for dv in data_views]
    lines.append(json.dumps(dashboard_so, separators=(",", ":")))
    return "\n".join(lines) + "\n"


def main():
    out_path = os.path.join(os.path.dirname(__file__), "connectivity-dashboard.ndjson")
    ndjson = generate_connectivity_dashboard_ndjson()
    with open(out_path, "w") as f:
        f.write(ndjson)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
