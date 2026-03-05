"""Mobile Gateway service — AWS us-east-1a. Mobile app API gateway & digital banking."""

from __future__ import annotations

import random
import time

from app.services.base_service import BaseService


class MobileGatewayService(BaseService):
    SERVICE_NAME = "mobile-gateway"

    def __init__(self, chaos_controller, otlp_client):
        super().__init__(chaos_controller, otlp_client)
        self._request_count = 0
        self._last_summary = time.time()
        self._api_endpoints = [
            "/api/v1/mobile/accounts",
            "/api/v1/mobile/transfer",
            "/api/v1/mobile/deposit",
            "/api/v1/mobile/pay-bills",
            "/api/v1/mobile/claims",
            "/api/v1/mobile/insurance",
        ]

    def generate_telemetry(self) -> None:
        active_channels = self.get_active_channels_for_service()
        for ch in active_channels:
            self.emit_fault_logs(ch)

        cascade_channels = self.get_cascade_channels_for_service()
        for ch in cascade_channels:
            self.emit_cascade_logs(ch)

        self._emit_api_request()
        self._emit_session_metrics()

        if time.time() - self._last_summary > 10:
            self._emit_gateway_summary()
            self._last_summary = time.time()

        latency_ms = round(random.uniform(15, 250), 1) if not active_channels else round(random.uniform(2000, 15000), 1)
        self.emit_metric("mobile_gateway.api_latency_ms", latency_ms, "ms")
        self.emit_metric("mobile_gateway.active_sessions", float(random.randint(8000, 15000)), "sessions")
        self.emit_metric("mobile_gateway.requests_per_sec", round(random.uniform(800, 2400), 1), "req/s")

    def _emit_api_request(self) -> None:
        self._request_count += 1
        endpoint = random.choice(self._api_endpoints)
        device = random.choice(["iPhone_15_Pro", "Samsung_S24", "iPad_Air", "Pixel_8"])
        latency_ms = round(random.uniform(20, 200), 1)
        self.emit_log(
            "INFO",
            f"[MOBILE] api_request endpoint={endpoint} device={device} latency_ms={latency_ms} status=200",
            {
                "operation": "api_request",
                "api.endpoint": endpoint,
                "api.device": device,
                "api.latency_ms": latency_ms,
                "api.status": 200,
            },
        )

    def _emit_session_metrics(self) -> None:
        active = random.randint(8000, 15000)
        self.emit_log(
            "INFO",
            f"[MOBILE] session_health active_sessions={active} auth_rate=99.2% platform=iOS/Android status=NOMINAL",
            {
                "operation": "session_health",
                "session.active": active,
                "session.auth_rate": 99.2,
            },
        )

    def _emit_gateway_summary(self) -> None:
        self.emit_log(
            "INFO",
            f"[MOBILE] gateway_summary total_requests={self._request_count} error_rate=0.02% uptime=99.99% status=NOMINAL",
            {
                "operation": "gateway_summary",
                "gateway.total_requests": self._request_count,
                "gateway.error_rate": 0.02,
            },
        )
