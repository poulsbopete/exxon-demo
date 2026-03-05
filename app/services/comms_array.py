"""Communications Array service — GCP us-central1. S-band, X-band, UHF antenna telemetry."""

from __future__ import annotations

import random

from app.services.base_service import BaseService


class CommsArrayService(BaseService):
    SERVICE_NAME = "comms-array"

    ANTENNAS = {
        "s_band": {
            "name": "S-Band",
            "nominal_signal_db_range": (18.0, 32.0),
            "nominal_packet_loss_range": (0.0, 0.5),
            "channels": ["S1", "S2", "S3"],
        },
        "x_band": {
            "name": "X-Band",
            "nominal_signal_db_range": (22.0, 38.0),
            "nominal_packet_loss_range": (0.0, 0.3),
            "channels": ["XB-PRIMARY", "XB-SECONDARY"],
        },
        "uhf": {
            "name": "UHF",
            "nominal_signal_db_range": (15.0, 28.0),
            "nominal_packet_loss_range": (0.0, 0.8),
            "channels": ["UHF-1", "UHF-2"],
        },
    }

    def generate_telemetry(self) -> None:
        # ── Fault injection ────────────────────────────────────
        active_channels = self.get_active_channels_for_service()
        for ch in active_channels:
            self.emit_fault_logs(ch)

        cascade_channels = self.get_cascade_channels_for_service()
        for ch in cascade_channels:
            self.emit_cascade_logs(ch)

        # ── Antenna telemetry ──────────────────────────────────
        for ant_key, ant in self.ANTENNAS.items():
            channel = random.choice(ant["channels"])
            signal_db = round(random.uniform(*ant["nominal_signal_db_range"]), 1)
            packet_loss = round(random.uniform(*ant["nominal_packet_loss_range"]), 2)

            self.emit_metric(f"comms.{ant_key}.signal_db", signal_db, "dB")
            self.emit_metric(f"comms.{ant_key}.packet_loss_pct", packet_loss, "%")

            self.emit_log(
                "INFO",
                f"[COMM] antenna={ant['name']} channel={channel} signal={signal_db}dB loss={packet_loss}% lock=ACQUIRED status=NOMINAL",
                {
                    "comms.antenna": ant["name"],
                    "comms.signal_db": signal_db,
                    "comms.packet_loss_pct": packet_loss,
                    "comms.channel": channel,
                    "operation": "antenna_check",
                },
            )

        # ── Link budget summary ────────────────────────────────
        total_throughput = round(random.uniform(45.0, 65.0), 1)
        self.emit_metric("comms.total_throughput_mbps", total_throughput, "Mbps")
        self.emit_log(
            "INFO",
            f"[COMM] link_budget throughput={total_throughput}Mbps margin=+3.2dB status=NOMINAL",
            {
                "operation": "link_budget",
                "comms.throughput_mbps": total_throughput,
                "comms.status": "NOMINAL",
            },
        )
