"""WiFi Controller service — GCP us-central1-b. Juniper Mist wireless LAN management."""

from __future__ import annotations

import random

from app.services.base_service import BaseService


class WifiControllerService(BaseService):
    SERVICE_NAME = "wifi-controller"

    AP_NAMES = [
        "AP-WAREHOUSE-01", "AP-WAREHOUSE-02", "AP-PRINT-FLOOR-01",
        "AP-OFFICE-01", "AP-OFFICE-02", "AP-SHIPPING-01",
    ]

    def generate_telemetry(self) -> None:
        # -- Fault injection --
        active_channels = self.get_active_channels_for_service()
        for ch in active_channels:
            self.emit_fault_logs(ch)

        cascade_channels = self.get_cascade_channels_for_service()
        for ch in cascade_channels:
            self.emit_cascade_logs(ch)

        # -- AP status polling --
        for ap in random.sample(self.AP_NAMES, k=min(3, len(self.AP_NAMES))):
            clients = random.randint(5, 45)
            channel = random.choice([1, 6, 11, 36, 40, 44, 48, 149, 153, 157, 161])
            signal_dbm = round(random.uniform(-65.0, -30.0), 1)
            noise_dbm = round(random.uniform(-95.0, -85.0), 1)

            self.emit_metric(f"wifi.ap.{ap.lower().replace('-', '_')}.clients", float(clients), "clients")
            self.emit_metric(f"wifi.ap.{ap.lower().replace('-', '_')}.signal_dbm", signal_dbm, "dBm")

            self.emit_log(
                "INFO",
                f"mist-event type=AP_STATS ap_name={ap} clients={clients} "
                f"channel={channel} signal={signal_dbm}dBm noise={noise_dbm}dBm",
                {
                    "operation": "ap_poll",
                    "wifi.ap_name": ap,
                    "wifi.clients": clients,
                    "wifi.channel": channel,
                    "wifi.signal_dbm": signal_dbm,
                    "wifi.noise_dbm": noise_dbm,
                },
            )

        # Controller summary
        total_clients = random.randint(80, 200)
        self.emit_metric("wifi.total_clients", float(total_clients), "clients")
        self.emit_log(
            "INFO",
            f"mist-event type=WLC_HEALTH aps_online={len(self.AP_NAMES)} "
            f"total_clients={total_clients} status=nominal",
            {
                "operation": "controller_health",
                "wifi.ap_count": len(self.AP_NAMES),
                "wifi.total_clients": total_clients,
            },
        )
