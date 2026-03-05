"""Elastic Observability Demo Platform — FastAPI entry point."""

from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import (
    ACTIVE_SCENARIO, APP_HOST, APP_PORT, CHANNEL_REGISTRY,
    MISSION_ID, MISSION_NAME, NAMESPACE, SERVICES,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
# Suppress noisy httpx request logging
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger("nova7")

# ── Multi-tenancy singletons ──────────────────────────────────────────────────
from app.registry import InstanceRegistry
from app.store import ChaosStore, DeploymentStore

registry = InstanceRegistry()
store = DeploymentStore()
chaos_store = ChaosStore()

# In-memory progress trackers keyed by deployment_id
_deploy_progress: dict[str, dict] = {}
_teardown_progress: dict[str, dict] = {}


def _get_instance(deployment_id: Optional[str] = None):
    """Look up instance by id, or return first active instance as fallback."""
    if deployment_id:
        inst = registry.get(deployment_id)
        if inst:
            return inst
    return registry.first()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """On startup: restore active deployments from SQLite.  On shutdown: stop all."""
    from app.context import ScenarioContext
    from app.instance import ScenarioInstance
    from scenarios import get_scenario

    # Restore previously active deployments
    for rec in store.get_all_active():
        try:
            scenario = get_scenario(rec["scenario_id"])
            ctx = ScenarioContext.from_scenario(
                scenario,
                otlp_endpoint=rec["otlp_endpoint"],
                otlp_api_key=rec["otlp_api_key"],
                elastic_url=rec["elastic_url"],
                elastic_api_key=rec["elastic_api_key"],
                kibana_url=rec["kibana_url"],
            )
            instance = ScenarioInstance(ctx, chaos_store=chaos_store)
            instance.start()
            registry.register(rec["deployment_id"], instance)
            logger.info("Restored deployment: %s (%s)", rec["deployment_id"], rec["scenario_id"])
        except Exception:
            logger.exception("Failed to restore deployment %s", rec["deployment_id"])
            store.set_status(rec["deployment_id"], "error")

    yield

    registry.stop_all()
    logger.info("All deployments shut down")


app = FastAPI(
    title="Elastic Observability Demo Platform",
    version="2.0.0",
    lifespan=lifespan,
)

# ── Static file mounts ─────────────────────────────────────────────────────
_base = os.path.dirname(__file__)
app.mount(
    "/dashboard/static",
    StaticFiles(directory=os.path.join(_base, "dashboard", "static")),
    name="dashboard-static",
)
app.mount(
    "/chaos/static",
    StaticFiles(directory=os.path.join(_base, "chaos_ui", "static")),
    name="chaos-static",
)
app.mount(
    "/landing/static",
    StaticFiles(directory=os.path.join(_base, "landing", "static")),
    name="landing-static",
)
app.mount(
    "/selector/static",
    StaticFiles(directory=os.path.join(_base, "selector", "static")),
    name="selector-static",
)

# ── Scenario helper ──────────────────────────────────────────────────────────

def _get_scenario_for_deployment(deployment_id: Optional[str] = None):
    """Get scenario object from a running instance or fall back to default."""
    inst = _get_instance(deployment_id)
    if inst:
        return inst.ctx.scenario
    from scenarios import get_scenario
    return get_scenario(ACTIVE_SCENARIO)


def _inject_theme(html: str, deployment_id: Optional[str] = None) -> str:
    """Inject active scenario's theme CSS vars and metadata into HTML."""
    inst = _get_instance(deployment_id)
    if inst:
        scenario = inst.ctx.scenario
        mission_id = inst.ctx.mission_id
        kibana = inst.ctx.kibana_url or _get_default_creds()[1]
    else:
        from scenarios import get_scenario
        scenario = get_scenario(ACTIVE_SCENARIO)
        mission_id = MISSION_ID
        kibana = _get_default_creds()[1]

    theme = scenario.theme

    # Build CSS that maps theme vars to the variable names used in existing stylesheets
    css_override = f""":root {{
{theme.to_css_vars()}
  --nominal: {theme.status_nominal};
  --advisory: {theme.status_warning};
  --caution: {theme.status_warning};
  --warning: {theme.status_warning};
  --critical: {theme.status_critical};
  --bg-card: {theme.bg_tertiary};
  --border: {theme.bg_tertiary};
  --text-dim: {theme.text_secondary};
}}
body {{ font-family: {theme.font_family}; }}"""

    replacements = {
        "<!--THEME_CSS-->": f"<style>{css_override}</style>",
        "DEPLOYMENT_ID_PLACEHOLDER": deployment_id or "",
        "SCENARIO_NAME_PLACEHOLDER": scenario.scenario_name,
        "SCENARIO_ID_PLACEHOLDER": scenario.scenario_id,
        "NAMESPACE_PLACEHOLDER": scenario.namespace,
        "MISSION_ID_PLACEHOLDER": mission_id,
        "DASHBOARD_TITLE_PLACEHOLDER": theme.dashboard_title,
        "CHAOS_TITLE_PLACEHOLDER": theme.chaos_title,
        "LANDING_TITLE_PLACEHOLDER": theme.landing_title,
        "KIBANA_URL_PLACEHOLDER": kibana,
    }
    for placeholder, value in replacements.items():
        html = html.replace(placeholder, value)
    return html


# ── Environment ──────────────────────────────────────────────────────────────

def _get_default_creds() -> tuple[str, str, str]:
    """Get (elastic_url, kibana_url, api_key).

    Priority:
    1. SQLite store (set after a successful /api/setup/launch)
    2. Environment variables injected by the Instruqt track setup script
       (DEFAULT_KIBANA_URL / DEFAULT_API_KEY) — available immediately on boot
       before any launch has been called.
    """
    recs = store.get_all_active()
    if recs:
        r = recs[0]
        return r["elastic_url"], r["kibana_url"], r["elastic_api_key"]

    # Fall back to env vars written by track setup into the systemd unit
    kibana = os.getenv("DEFAULT_KIBANA_URL", "").strip().rstrip("/")
    key = os.getenv("DEFAULT_API_KEY", "").strip()
    if kibana and key:
        elastic = kibana.replace(".kb.", ".es.") if ".kb." in kibana else ""
        return elastic, kibana, key

    return "", "", ""


# ── Scenario Selector (new front page) ───────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def selector_page():
    """Scenario selector — choose industry vertical and connect."""
    path = os.path.join(_base, "selector", "static", "index.html")
    if os.path.exists(path):
        with open(path) as f:
            return HTMLResponse(content=f.read())
    # Fallback to legacy landing if selector not yet built
    return await landing_page()


# ── Per-Scenario Landing Page ─────────────────────────────────────────────────

@app.get("/home", response_class=HTMLResponse)
async def landing_page(deployment_id: Optional[str] = None):
    """Scenario-specific landing page with themed links."""
    path = os.path.join(_base, "landing", "static", "index.html")
    with open(path) as f:
        html = f.read()
    return HTMLResponse(content=_inject_theme(html, deployment_id))


@app.get("/slides", response_class=HTMLResponse)
async def slides_page(deployment_id: Optional[str] = None):
    path = os.path.join(_base, "landing", "static", "slides.html")
    with open(path) as f:
        html = f.read()
    return HTMLResponse(content=_inject_theme(html, deployment_id))


# ── Health ──────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    instances = registry.all_instances()
    return {
        "status": "ok",
        "deployments": len(instances),
        "scenarios": [dep_id for dep_id in instances],
    }


# ── Dashboard ───────────────────────────────────────────────────────────────

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(deployment_id: Optional[str] = None):
    path = os.path.join(_base, "dashboard", "static", "index.html")
    with open(path) as f:
        html = f.read()
    return HTMLResponse(content=_inject_theme(html, deployment_id))


@app.websocket("/ws/dashboard")
async def ws_dashboard(websocket: WebSocket):
    inst = _get_instance()
    if not inst:
        await websocket.close(1000)
        return
    await inst.dashboard_ws.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        inst.dashboard_ws.disconnect(websocket)


# ── Chaos Controller UI ────────────────────────────────────────────────────

@app.get("/chaos", response_class=HTMLResponse)
async def chaos_page(deployment_id: Optional[str] = None):
    path = os.path.join(_base, "chaos_ui", "static", "index.html")
    with open(path) as f:
        html = f.read()
    return HTMLResponse(content=_inject_theme(html, deployment_id))


# ── Scenario API ───────────────────────────────────────────────────────────

@app.get("/api/scenarios")
async def list_scenarios():
    """List all available scenarios."""
    from scenarios import list_scenarios as _list
    return _list()


@app.get("/api/scenario")
async def current_scenario(deployment_id: Optional[str] = None):
    """Return active scenario metadata and theme."""
    scenario = _get_scenario_for_deployment(deployment_id)
    theme = scenario.theme
    return {
        "id": scenario.scenario_id,
        "name": scenario.scenario_name,
        "description": scenario.scenario_description,
        "namespace": scenario.namespace,
        "services": scenario.services,
        "channel_registry": {
            str(k): {
                "name": v["name"],
                "subsystem": v["subsystem"],
                "error_type": v["error_type"],
                "affected_services": v["affected_services"],
                "cascade_services": v["cascade_services"],
                "description": v["description"],
            }
            for k, v in scenario.channel_registry.items()
        },
        "theme": {
            "bg_primary": theme.bg_primary,
            "bg_secondary": theme.bg_secondary,
            "bg_tertiary": theme.bg_tertiary,
            "accent_primary": theme.accent_primary,
            "accent_secondary": theme.accent_secondary,
            "text_primary": theme.text_primary,
            "text_secondary": theme.text_secondary,
            "text_accent": theme.text_accent,
            "status_nominal": theme.status_nominal,
            "status_warning": theme.status_warning,
            "status_critical": theme.status_critical,
            "dashboard_title": theme.dashboard_title,
            "chaos_title": theme.chaos_title,
            "landing_title": theme.landing_title,
            "font_family": theme.font_family,
            "font_mono": theme.font_mono,
            "scanline_effect": theme.scanline_effect,
            "glow_effect": theme.glow_effect,
            "grid_background": theme.grid_background,
            "gradient_accent": theme.gradient_accent,
        },
        "countdown": {
            "enabled": scenario.countdown_config.enabled,
            "start_seconds": scenario.countdown_config.start_seconds,
        },
    }


# ── Deployments API (multi-tenancy) ──────────────────────────────────────────

@app.get("/api/deployments")
async def list_deployments():
    """List all active deployments."""
    instances = registry.all_instances()
    result = []
    for dep_id, inst in instances.items():
        result.append({
            "deployment_id": dep_id,
            "scenario_id": inst.scenario_id,
            "scenario_name": inst.ctx.scenario.scenario_name,
            "namespace": inst.ctx.namespace,
            "running": inst.running,
            "kibana_url": inst.ctx.kibana_url,
        })
    return result


@app.post("/api/deployments/{deployment_id}/stop")
async def stop_deployment(deployment_id: str):
    """Stop a specific deployment's generators."""
    inst = registry.get(deployment_id)
    if not inst:
        return JSONResponse(status_code=404, content={"error": f"Deployment {deployment_id} not found"})
    inst.stop()
    store.set_status(deployment_id, "stopped")
    return {"status": "stopped", "deployment_id": deployment_id}


@app.delete("/api/deployments/{deployment_id}")
async def remove_deployment(deployment_id: str):
    """Remove a deployment from registry and store."""
    inst = registry.remove(deployment_id)
    if inst:
        inst.stop()
    store.delete(deployment_id)
    return {"status": "removed", "deployment_id": deployment_id}


# ── Chaos API ───────────────────────────────────────────────────────────────

@app.post("/api/chaos/trigger")
async def chaos_trigger(body: dict):
    deployment_id = body.get("deployment_id")
    inst = _get_instance(deployment_id)
    if not inst:
        return JSONResponse(status_code=404, content={"error": "No active deployment"})
    channel = int(body.get("channel", 0))
    mode = body.get("mode", "calibration")
    se_name = body.get("se_name", "")
    callback_url = body.get("callback_url", "")
    user_email = body.get("user_email", "")
    session_id = body.get("session_id", "")
    result = inst.chaos_controller.trigger(
        channel, mode, se_name, callback_url, user_email, session_id=session_id,
    )
    if inst.dashboard_ws:
        await inst.dashboard_ws.broadcast_status(inst.chaos_controller, inst.service_manager)

    # Immediately emit fault ERROR logs so alert rules fire within 1 minute.
    # We fire-and-forget in a background thread to keep the HTTP response fast.
    try:
        import threading as _threading
        _threading.Thread(
            target=_emit_fault_logs,
            args=(inst, channel),
            daemon=True,
        ).start()
    except Exception as _exc:
        logger.warning("fault-log emit failed to start: %s", _exc)

    return result


def _emit_fault_logs(inst, channel: int, interval: float = 20.0) -> None:
    """Write fault-alert documents directly to Elasticsearch every `interval` seconds.

    Runs until the channel is no longer active (user clicked Resolve or auto-expiry).
    Uses fault-events-exxon (plain index, not a data stream) which auto-creates in
    Elastic Serverless because arbitrary index creation is allowed.
    """
    import time as _time
    import random as _random
    import httpx as _httpx

    try:
        ctx = getattr(inst, "ctx", None)
        if not ctx:
            return

        es_url = (ctx.elastic_url or "").rstrip("/")
        api_key = ctx.elastic_api_key or ""
        if not es_url or not api_key:
            logger.warning("_emit_fault_logs: missing ES credentials (url=%r)", es_url[:30])
            return

        channel_registry = ctx.channel_registry or {}
        namespace = ctx.namespace or "demo"
        ch = channel_registry.get(channel, {})
        if not ch:
            return

        error_type = ch.get("error_type", "unknown")
        log_messages = ch.get("log_messages", [])
        affected = ch.get("affected_services", [])
        service_name = affected[0] if affected else "fault-emitter"
        # Use the plain index name — confirmed to auto-create in this Serverless deployment
        index = f"fault-events-{namespace}"
        headers = {
            "Authorization": f"ApiKey {api_key}",
            "Content-Type": "application/json",
        }
        url = f"{es_url}/{index}/_doc"
        chaos = inst.chaos_controller

        logger.info("fault-log-emitter: starting for channel=%d error_type=%s", channel, error_type)
        with _httpx.Client(timeout=10, verify=True) as http:
            while True:
                # Stop when channel is no longer active
                active = chaos.get_active_channels() if chaos else []
                if channel not in active:
                    logger.info("fault-log-emitter: channel %d resolved, stopping", channel)
                    break

                msg = _random.choice(log_messages) if log_messages else error_type
                doc = {
                    "@timestamp": _time.strftime("%Y-%m-%dT%H:%M:%S.000Z", _time.gmtime()),
                    "fault.channel": channel,
                    "fault.error_type": error_type,
                    "fault.name": ch.get("name", ""),
                    "service.name": service_name,
                    "severity_text": "ERROR",
                    "message": f"[fault-channel-{channel}] {error_type}: {msg}",
                }
                try:
                    resp = http.post(url, json=doc, headers=headers)
                    if resp.status_code < 300:
                        logger.debug("fault-event indexed: ch=%d %s", channel, error_type)
                    else:
                        logger.warning("fault-event index failed HTTP %d: %s", resp.status_code, resp.text[:150])
                except Exception as send_exc:  # noqa: BLE001
                    logger.warning("fault-log-emitter send error: %s", send_exc)

                _time.sleep(interval)
    except Exception as exc:  # noqa: BLE001
        logger.warning("_emit_fault_logs error: %s", exc)


@app.post("/api/chaos/resolve")
async def chaos_resolve(body: dict):
    deployment_id = body.get("deployment_id")
    inst = _get_instance(deployment_id)
    if not inst:
        return JSONResponse(status_code=404, content={"error": "No active deployment"})
    channel = int(body.get("channel", 0))
    session_id = body.get("session_id", "")
    result = inst.chaos_controller.resolve(channel, session_id=session_id)
    if result.get("error") == "session_mismatch":
        return JSONResponse(status_code=403, content=result)
    if inst.dashboard_ws:
        await inst.dashboard_ws.broadcast_status(inst.chaos_controller, inst.service_manager)
    return result


@app.post("/api/chaos/spikes")
async def set_chaos_spikes(body: dict):
    deployment_id = body.get("deployment_id")
    inst = _get_instance(deployment_id)
    if not inst:
        return JSONResponse(status_code=404, content={"error": "No active deployment"})
    inst.chaos_controller.set_infra_spikes(body)
    return inst.chaos_controller.get_infra_spikes()


@app.get("/api/chaos/spikes")
async def get_chaos_spikes(deployment_id: Optional[str] = None):
    inst = _get_instance(deployment_id)
    if not inst:
        return {"cpu_pct": 0, "memory_pct": 0, "k8s_oom_intensity": 0, "latency_multiplier": 1.0}
    return inst.chaos_controller.get_infra_spikes()


@app.get("/api/chaos/status")
async def chaos_status(deployment_id: Optional[str] = None):
    inst = _get_instance(deployment_id)
    if not inst:
        return {}
    return inst.chaos_controller.get_status()


@app.get("/api/chaos/status/{channel}")
async def chaos_channel_status(channel: int, deployment_id: Optional[str] = None):
    inst = _get_instance(deployment_id)
    if not inst:
        return {"error": "No active deployment"}
    return inst.chaos_controller.get_channel_status(channel)


@app.get("/api/chaos/session/validate")
async def chaos_session_validate(session_id: str, deployment_id: Optional[str] = None):
    """Check if a session_id owns any active channels."""
    inst = _get_instance(deployment_id)
    if not inst:
        return {"valid": False, "channels": []}
    channels = inst.chaos_controller.validate_session(session_id)
    return {"valid": len(channels) > 0, "channels": channels}


# ── Status API ──────────────────────────────────────────────────────────────

@app.get("/api/status")
async def system_status(deployment_id: Optional[str] = None):
    inst = _get_instance(deployment_id)
    if not inst:
        return {"error": "No active deployment"}
    return {
        "scenario": inst.scenario_id,
        "mission_id": inst.ctx.mission_id,
        "mission_name": inst.ctx.scenario.scenario_name,
        "namespace": inst.ctx.namespace,
        "services": inst.service_manager.get_all_status(),
        "generators": inst.service_manager.get_generator_status(),
        "chaos": inst.chaos_controller.get_status(),
        "countdown": inst.service_manager.get_countdown(),
    }


# ── Countdown Control ──────────────────────────────────────────────────────

@app.post("/api/countdown/start")
async def countdown_start(body: dict = {}):
    inst = _get_instance(body.get("deployment_id") if body else None)
    if not inst:
        return JSONResponse(status_code=404, content={"error": "No active deployment"})
    inst.service_manager.countdown_start()
    return {"status": "started"}


@app.post("/api/countdown/pause")
async def countdown_pause(body: dict = {}):
    inst = _get_instance(body.get("deployment_id") if body else None)
    if not inst:
        return JSONResponse(status_code=404, content={"error": "No active deployment"})
    inst.service_manager.countdown_pause()
    return {"status": "paused"}


@app.post("/api/countdown/reset")
async def countdown_reset(body: dict = {}):
    inst = _get_instance(body.get("deployment_id") if body else None)
    if not inst:
        return JSONResponse(status_code=404, content={"error": "No active deployment"})
    inst.service_manager.countdown_reset()
    return {"status": "reset"}


@app.post("/api/countdown/speed")
async def countdown_speed(body: dict):
    inst = _get_instance(body.get("deployment_id"))
    if not inst:
        return JSONResponse(status_code=404, content={"error": "No active deployment"})
    speed = float(body.get("speed", 1.0))
    inst.service_manager.countdown_set_speed(speed)
    return {"status": "speed_set", "speed": speed}


# ── Remediation endpoint (called by Elastic Workflow) ──────────────────────

@app.post("/api/remediate/{channel}")
async def remediate_channel(channel: int, deployment_id: Optional[str] = None):
    inst = _get_instance(deployment_id)
    if not inst:
        return JSONResponse(status_code=404, content={"error": "No active deployment"})
    result = inst.chaos_controller.resolve(channel, force=True)
    if inst.dashboard_ws:
        await inst.dashboard_ws.broadcast_status(inst.chaos_controller, inst.service_manager)
    return {"action": "remediated", "channel": channel, **result}


# ── User Info (for auto-populating email) ─────────────────────────────────

@app.get("/api/user/info")
async def user_info(request: Request):
    email = request.headers.get("X-Forwarded-User", "")
    return {"email": email}


# ── Email Notification endpoint (called by Elastic Workflow) ──────────────

@app.post("/api/notify/email")
async def notify_email(body: dict):
    from app.notify.email_handler import send_email

    to = body.get("to", "")
    subject = body.get("subject", "")
    message = body.get("body", "")
    result = await send_email(to, subject, message)
    return result


# ── Daily Update Report ────────────────────────────────────────────────────

@app.post("/api/daily-update")
async def send_daily_update(body: dict):
    """Trigger the Daily Update Report workflow, which uses the AI assistant
    to analyse recent logs/traces and emails a health summary."""
    import httpx as _httpx

    email = body.get("email", "").strip()
    deployment_id = body.get("deployment_id")

    if not email:
        return JSONResponse(status_code=400, content={"error": "Missing email"})

    inst = _get_instance(deployment_id)
    if not inst:
        return JSONResponse(status_code=404, content={"error": "No active deployment"})

    kibana_url = inst.ctx.kibana_url
    api_key = inst.ctx.elastic_api_key
    if not kibana_url or not api_key:
        return JSONResponse(status_code=400, content={"error": "No Kibana credentials"})

    headers = {
        "Content-Type": "application/json",
        "kbn-xsrf": "true",
        "x-elastic-internal-origin": "kibana",
        "Authorization": f"ApiKey {api_key}",
    }

    async with _httpx.AsyncClient(timeout=30) as client:
        # Find the workflow by name
        search_resp = await client.post(
            f"{kibana_url}/api/workflows/search",
            headers=headers,
            json={"page": 1, "size": 100},
        )
        if search_resp.status_code >= 300:
            return JSONResponse(
                status_code=502,
                content={"error": f"Workflow search failed: {search_resp.status_code}"},
            )

        search_data = search_resp.json()
        workflows = search_data.get("results", search_data.get("data", []))
        wf_id = None
        for wf in workflows:
            if "Daily Update Report" in wf.get("name", ""):
                wf_id = wf["id"]
                break

        if not wf_id:
            return JSONResponse(
                status_code=404,
                content={"error": "Daily Update Report workflow not found — redeploy the scenario"},
            )

        # Trigger the workflow
        run_resp = await client.post(
            f"{kibana_url}/api/workflows/{wf_id}/run",
            headers=headers,
            json={"inputs": {"email": email}},
        )
        if run_resp.status_code >= 300:
            return JSONResponse(
                status_code=502,
                content={"error": f"Workflow run failed: {run_resp.status_code}"},
            )

    return {
        "status": "triggered",
        "message": "Daily update report requested — check your email in 2-3 minutes",
        "workflow_id": wf_id,
    }


# ── Setup / Deployer API ───────────────────────────────────────────────────

@app.post("/api/setup/test-connection")
async def test_connection(body: dict):
    """Test connectivity to an Elastic environment."""
    from scenarios import get_scenario as _get_scenario_by_id
    from elastic_config.deployer import ScenarioDeployer

    kibana_url = body.get("kibana_url", "").strip().rstrip("/")
    api_key = body.get("api_key", "").strip()

    if not kibana_url or not api_key:
        return {"ok": False, "error": "Missing kibana_url or api_key"}

    # Derive ES URL from Kibana URL unless explicitly provided
    elastic_url = (body.get("elastic_url") or "").strip().rstrip("/")
    if not elastic_url and ".kb." in kibana_url:
        elastic_url = kibana_url.replace(".kb.", ".es.")

    if not elastic_url:
        return {"ok": False, "error": "Cannot derive Elasticsearch URL — provide it in Advanced settings"}

    # Derive OTLP endpoint
    otlp_url = body.get("otlp_url") or ""
    if not otlp_url and ".kb." in kibana_url:
        otlp_url = kibana_url.replace(".kb.", ".ingest.").rstrip("/")
        if not otlp_url.endswith(":443"):
            otlp_url += ":443"

    scenario_id = body.get("scenario_id", ACTIVE_SCENARIO)
    scenario = _get_scenario_by_id(scenario_id)
    deployer = ScenarioDeployer(scenario, elastic_url, kibana_url, api_key)
    result = deployer.check_connection()

    # Also verify OTLP if we have an endpoint
    if result.get("ok") and otlp_url:
        otlp_ok = deployer.verify_otlp(otlp_url)
        result["otlp_endpoint"] = otlp_url if otlp_ok else None
        result["otlp_ok"] = otlp_ok
    else:
        result["otlp_endpoint"] = None
        result["otlp_ok"] = False

    result["elastic_url"] = elastic_url
    return result


@app.get("/api/setup/defaults")
async def setup_defaults():
    """Return pre-provisioned credentials from the SQLite store.

    Instruqt track setup calls /api/setup/launch with the Elastic Cloud
    credentials immediately after provisioning.  The selector UI fetches
    this endpoint on load so it can pre-populate the connection form without
    the learner having to paste anything.
    """
    elastic_url, kibana_url, api_key = _get_default_creds()
    if not kibana_url or not api_key:
        return JSONResponse(status_code=204, content=None)
    otlp_url = ""
    if kibana_url and ".kb." in kibana_url:
        otlp_url = kibana_url.replace(".kb.", ".ingest.").rstrip("/")
        if not otlp_url.endswith(":443"):
            otlp_url += ":443"
    return {
        "kibana_url": kibana_url,
        "api_key": api_key,
        "elastic_url": elastic_url,
        "otlp_url": otlp_url,
        "scenario_id": ACTIVE_SCENARIO,
    }


@app.post("/api/setup/launch")
async def launch_setup(body: dict):
    """Launch deployment of a scenario to Elastic.

    Accepts scenario_id + kibana_url + api_key.  Derives ES and OTLP URLs.
    Runs in a background thread. After deployment, creates a ScenarioInstance
    and registers it in the registry + SQLite store.
    """
    import threading

    from scenarios import get_scenario as _get_scenario_by_id
    from elastic_config.deployer import ScenarioDeployer
    from app.context import ScenarioContext
    from app.instance import ScenarioInstance

    scenario_id = body.get("scenario_id", ACTIVE_SCENARIO)
    _def_elastic, _def_kibana, _def_key = _get_default_creds()
    kibana_url = body.get("kibana_url", _def_kibana).strip().rstrip("/")
    api_key = body.get("api_key", _def_key).strip()

    # Derive ES URL from Kibana URL unless explicitly provided
    elastic_url = (body.get("elastic_url") or "").strip().rstrip("/")
    if not elastic_url and ".kb." in kibana_url:
        elastic_url = kibana_url.replace(".kb.", ".es.")
    if not elastic_url:
        elastic_url = _def_elastic

    if not kibana_url or not api_key:
        return JSONResponse(
            status_code=400,
            content={"error": "Missing kibana_url or api_key"},
        )

    # Explicit OTLP override from Advanced settings
    explicit_otlp = body.get("otlp_url") or ""

    scenario = _get_scenario_by_id(scenario_id)
    deployer = ScenarioDeployer(scenario, elastic_url, kibana_url, api_key)

    # Use scenario_id as deployment_id
    deployment_id = scenario_id

    def _progress_cb(progress):
        _deploy_progress[deployment_id] = progress.to_dict()

    def _run():
        # Stop existing instance for this scenario if running
        old_inst = registry.get(deployment_id)
        if old_inst:
            try:
                old_inst.stop()
                logger.info("Stopped existing instance %s before redeploy", deployment_id)
            except Exception as exc:
                logger.warning("Error stopping old instance: %s", exc)

        result = deployer.deploy_all(callback=_progress_cb)

        # Use explicit OTLP override if provided, otherwise use derived
        otlp_endpoint = explicit_otlp or result.otlp_endpoint

        # Create ScenarioContext + ScenarioInstance
        try:
            ctx = ScenarioContext.from_scenario(
                scenario,
                otlp_endpoint=otlp_endpoint or "",
                otlp_api_key=api_key,
                elastic_url=elastic_url,
                elastic_api_key=api_key,
                kibana_url=kibana_url,
            )
            instance = ScenarioInstance(ctx, chaos_store=chaos_store)

            # Reconfigure OTLP if we have an endpoint
            if otlp_endpoint:
                instance.otlp.reconfigure(otlp_endpoint, api_key)
                logger.info("OTLPClient for %s reconfigured to %s", scenario_id, otlp_endpoint)

            instance.start()
            registry.register(deployment_id, instance)

            # Persist to SQLite
            store.upsert(
                deployment_id=deployment_id,
                scenario_id=scenario_id,
                otlp_endpoint=otlp_endpoint or "",
                otlp_api_key=api_key,
                elastic_url=elastic_url,
                elastic_api_key=api_key,
                kibana_url=kibana_url,
            )

            logger.info("Deployment %s (%s) live", deployment_id, scenario_id)
        except Exception as exc:
            logger.exception("Failed to start instance for %s: %s", scenario_id, exc)

    _deploy_progress[deployment_id] = {"finished": False, "error": "", "steps": []}
    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    return {"status": "started", "scenario": scenario_id, "deployment_id": deployment_id}


@app.get("/api/setup/progress")
async def setup_progress(deployment_id: Optional[str] = None):
    """Return current deployment progress."""
    if deployment_id and deployment_id in _deploy_progress:
        return _deploy_progress[deployment_id]
    # Fall back to most recent progress entry
    if _deploy_progress:
        return list(_deploy_progress.values())[-1]
    return {"finished": True, "error": "", "steps": []}


@app.get("/api/setup/detect")
async def detect_existing(deployment_id: Optional[str] = None):
    """Check if the active scenario is already deployed to Elastic."""
    from elastic_config.deployer import ScenarioDeployer

    # Try to use credentials from a specific deployment
    inst = _get_instance(deployment_id)
    if inst and inst.ctx.elastic_url and inst.ctx.elastic_api_key:
        elastic_url = inst.ctx.elastic_url
        kibana_url = inst.ctx.kibana_url
        api_key = inst.ctx.elastic_api_key
        scenario = inst.ctx.scenario
    else:
        elastic_url, kibana_url, api_key = _get_default_creds()
        scenario = _get_scenario_for_deployment(deployment_id)

    if not elastic_url or not api_key:
        return {"deployed": False, "error": "No Elastic credentials configured"}

    deployer = ScenarioDeployer(scenario, elastic_url, kibana_url, api_key)
    return deployer.detect_existing()


@app.post("/api/setup/teardown")
async def teardown_setup(body: dict = {}):
    """Remove a scenario's Elastic config (KB, workflows, alerts, etc)."""
    from elastic_config.deployer import ScenarioDeployer

    deployment_id = body.get("deployment_id") if body else None
    inst = _get_instance(deployment_id)

    if inst and inst.ctx.elastic_url and inst.ctx.elastic_api_key:
        elastic_url = inst.ctx.elastic_url
        kibana_url = inst.ctx.kibana_url
        api_key = inst.ctx.elastic_api_key
        scenario = inst.ctx.scenario
    else:
        elastic_url, kibana_url, api_key = _get_default_creds()
        scenario = _get_scenario_for_deployment(deployment_id)

    if not elastic_url or not api_key:
        return JSONResponse(
            status_code=400,
            content={"error": "No Elastic credentials configured"},
        )

    deployer = ScenarioDeployer(scenario, elastic_url, kibana_url, api_key)
    return deployer.teardown()


@app.post("/api/setup/stop-and-teardown")
async def stop_and_teardown(body: dict = {}):
    """Stop generators and remove scenario artifacts from Elastic (async with progress)."""
    import threading

    from elastic_config.deployer import ScenarioDeployer

    deployment_id = body.get("deployment_id") if body else None

    if deployment_id:
        # Stop specific deployment — remove from registry and stop generators synchronously
        inst = registry.remove(deployment_id)
        if inst:
            try:
                inst.stop()
                logger.info("Stopped deployment %s via stop-and-teardown", deployment_id)
            except Exception as exc:
                logger.warning("Error stopping deployment %s: %s", deployment_id, exc)

            # Run teardown in background thread with progress
            if inst.ctx.elastic_url and inst.ctx.elastic_api_key:
                deployer = ScenarioDeployer(
                    inst.ctx.scenario, inst.ctx.elastic_url,
                    inst.ctx.kibana_url, inst.ctx.elastic_api_key,
                )

                def _progress_cb(progress):
                    _teardown_progress[deployment_id] = progress.to_dict()

                def _run_teardown():
                    deployer.teardown_with_progress(callback=_progress_cb)
                    store.delete(deployment_id)

                _teardown_progress[deployment_id] = {"finished": False, "error": "", "steps": []}
                thread = threading.Thread(target=_run_teardown, daemon=True)
                thread.start()

                return {"status": "stopping", "deployment_id": deployment_id}

        store.delete(deployment_id)
        # No credentials — mark as instantly done
        _teardown_progress[deployment_id] = {"finished": True, "error": "", "steps": []}
        return {"status": "stopping", "deployment_id": deployment_id}
    else:
        # Stop ALL deployments
        registry.stop_all()
        logger.info("All generators stopped via stop-and-teardown")

        # Clean up ALL scenario artifacts using first available credentials
        elastic_url, kibana_url, api_key = _get_default_creds()

        if not elastic_url or not api_key:
            return {"ok": True, "generators_stopped": True, "artifacts_deleted": 0,
                    "note": "No Elastic credentials — generators stopped but no artifacts to clean"}

        result = ScenarioDeployer.cleanup_all(elastic_url, kibana_url, api_key)

        # Clear all deployment records from store
        for rec in store.get_all_active():
            store.delete(rec["deployment_id"])

        return {
            "ok": result.get("ok", False),
            "generators_stopped": True,
            "artifacts_deleted": result.get("deleted", 0),
            "error": result.get("error", ""),
        }


@app.get("/api/check/{challenge}")
async def challenge_check(challenge: int):
    """Server-side check for Instruqt challenge validation.

    Returns JSON {"ok": bool, "reason": str} so check scripts stay simple
    and never need ES credentials themselves.

    Challenge 1: deployment finished (all setup steps completed).
    Challenge 2: SNMP trap data present in Elastic (≥3 docs in snmp index).
    Challenge 3: knowledge base indexed (≥4 docs in kb index).
    """
    import httpx as _httpx

    # --- shared: must have a running exxon deployment ---
    instances = registry.all_instances()
    inst = None
    for _, i in instances.items():
        if "exxon" in (i.ctx.namespace or "").lower() or "exxon" in (i.scenario_id or "").lower():
            inst = i
            break

    if not inst:
        return {"ok": False, "reason": "No Exxon deployment found. Open the Demo App and start the scenario."}

    if challenge == 1:
        # Must have finished all setup steps
        prog = _deploy_progress.get(inst.deployment_id, {})
        finished = prog.get("finished", False)
        if not finished:
            steps = prog.get("steps", [])
            done = sum(1 for s in steps if s.get("status") in ("ok", "skipped", "warn", "warning"))
            total = len(steps)
            return {"ok": False, "reason": f"Deployment still in progress ({done}/{total} steps). Wait for all steps to complete."}
        return {"ok": True, "reason": "Deployment complete."}

    es_url = (inst.ctx.elastic_url or "").rstrip("/")
    api_key = inst.ctx.elastic_api_key or ""
    if not es_url or not api_key:
        elastic_url, _, api_key = _get_default_creds()
        es_url = (elastic_url or "").rstrip("/")

    if not es_url or not api_key:
        return {"ok": False, "reason": "No Elastic credentials available yet. Wait for deployment to complete."}

    headers = {"Authorization": f"ApiKey {api_key}", "Content-Type": "application/json"}

    if challenge == 2:
        # SNMP trap data must be in Elastic (loaded by Challenge 2 setup script)
        try:
            with _httpx.Client(timeout=10, verify=True) as http:
                # Check multiple possible index names (Elastic may route differently)
                count = 0
                for idx in ["logs-snmp.trap-exxon", "logs-snmp*", "logs*"]:
                    resp = http.post(
                        f"{es_url}/{idx}/_count",
                        headers=headers,
                        json={"query": {"exists": {"field": "snmp.trap.type"}}},
                    )
                    if resp.status_code < 300:
                        count = resp.json().get("count", 0)
                        if count > 0:
                            break
                if count >= 3:
                    return {"ok": True, "reason": f"{count} SNMP trap events found in Elastic."}
                return {"ok": False, "reason": f"Only {count} SNMP trap events found (need ≥3). The setup script should have loaded them automatically — if this persists, try restarting the challenge."}
        except Exception as exc:
            return {"ok": False, "reason": f"Could not query Elastic: {exc}"}

    if challenge == 3:
        # Knowledge base must be populated
        try:
            with _httpx.Client(timeout=10, verify=True) as http:
                ns = inst.ctx.namespace or "exxon"
                resp = http.get(f"{es_url}/{ns}-knowledge-base/_count", headers=headers)
                count = resp.json().get("count", 0) if resp.status_code < 300 else 0
                if count >= 4:
                    return {"ok": True, "reason": f"Knowledge base has {count} documents."}
                return {"ok": False, "reason": f"Knowledge base only has {count} documents (need ≥4). Deployment may not be complete."}
        except Exception as exc:
            return {"ok": False, "reason": f"Could not query Elastic: {exc}"}

    return {"ok": False, "reason": f"Unknown challenge number: {challenge}"}


@app.get("/api/setup/teardown-progress")
async def teardown_progress(deployment_id: Optional[str] = None):
    """Return current teardown progress."""
    if deployment_id and deployment_id in _teardown_progress:
        return _teardown_progress[deployment_id]
    if _teardown_progress:
        return list(_teardown_progress.values())[-1]
    return {"finished": True, "error": "", "steps": []}


# ── Run ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=APP_HOST, port=APP_PORT, reload=False)
