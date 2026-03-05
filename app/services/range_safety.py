"""Range Safety service — Azure eastus. Flight safety monitoring."""

from __future__ import annotations

import random

from app.services.base_service import BaseService


class RangeSafetyService(BaseService):
    SERVICE_NAME = "range-safety"

    SAFETY_CHECKS = [
        {"name": "flight_termination_system", "description": "FTS self-test"},
        {"name": "tracking_radar", "description": "Vehicle tracking acquisition"},
        {"name": "telemetry_link", "description": "Telemetry data link integrity"},
        {"name": "destruct_package", "description": "Destruct system status"},
        {"name": "boundary_corridor", "description": "Flight corridor boundaries"},
        {"name": "populated_area_clearance", "description": "Populated area safety margin"},
        {"name": "debris_footprint", "description": "Predicted debris footprint"},
    ]

    def generate_telemetry(self) -> None:
        # ── Fault injection ────────────────────────────────────
        active_channels = self.get_active_channels_for_service()
        for ch in active_channels:
            self.emit_fault_logs(ch)

        cascade_channels = self.get_cascade_channels_for_service()
        for ch in cascade_channels:
            self.emit_cascade_logs(ch)

        # ── Safety checks ──────────────────────────────────────
        checks_to_run = random.sample(
            self.SAFETY_CHECKS, k=min(4, len(self.SAFETY_CHECKS))
        )
        for check in checks_to_run:
            margin = round(random.uniform(15.0, 95.0), 1)
            self.emit_log(
                "INFO",
                f"[RSO] check={check['name']} margin={margin}% result=PASS status=NOMINAL",
                {
                    "safety.check": check["name"],
                    "safety.status": "PASS",
                    "safety.margin_pct": margin,
                    "safety.description": check["description"],
                    "operation": "safety_check",
                },
            )
            self.emit_metric(
                f"range_safety.{check['name']}_margin", margin, "%"
            )

        # ── Tracking status ────────────────────────────────────
        track_quality = round(random.uniform(0.92, 1.0), 4)
        radar_count = random.randint(2, 4)
        self.emit_metric("range_safety.track_quality", track_quality, "ratio")
        self.emit_metric("range_safety.active_radars", float(radar_count), "count")
        self.emit_log(
            "INFO",
            f"[RSO] tracking radars={radar_count} quality={track_quality} corridor=WITHIN status=NOMINAL",
            {
                "operation": "tracking_status",
                "safety.radar_count": radar_count,
                "safety.track_quality": track_quality,
                "safety.status": "NOMINAL",
            },
        )
