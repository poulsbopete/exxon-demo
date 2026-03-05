"""Packaging Fulfillment service — GCP us-central1-a. Warehouse operations and shipping."""

from __future__ import annotations

import random

from app.services.base_service import BaseService


class PackagingFulfillmentService(BaseService):
    SERVICE_NAME = "packaging-fulfillment"

    def generate_telemetry(self) -> None:
        # -- Fault injection --
        active_channels = self.get_active_channels_for_service()
        for ch in active_channels:
            self.emit_fault_logs(ch)

        cascade_channels = self.get_cascade_channels_for_service()
        for ch in cascade_channels:
            self.emit_cascade_logs(ch)

        # -- Fulfillment metrics --
        orders_pending = random.randint(50, 400)
        labels_printed = random.randint(200, 800)
        scan_accuracy = round(random.uniform(99.2, 100.0), 2)
        pick_rate = round(random.uniform(120.0, 250.0), 1)

        self.emit_metric("fulfillment.orders_pending", float(orders_pending), "orders")
        self.emit_metric("fulfillment.labels_printed", float(labels_printed), "labels")
        self.emit_metric("fulfillment.scan_accuracy_pct", scan_accuracy, "%")
        self.emit_metric("fulfillment.pick_rate", pick_rate, "items/hr")

        self.emit_log(
            "INFO",
            f"wms.fulfillment orders_pending={orders_pending} labels_printed={labels_printed} "
            f"scan_accuracy={scan_accuracy}% pick_rate={pick_rate}/hr",
            {
                "operation": "fulfillment_health",
                "fulfillment.pending": orders_pending,
                "fulfillment.labels": labels_printed,
                "fulfillment.scan_accuracy": scan_accuracy,
                "fulfillment.pick_rate": pick_rate,
            },
        )

        # Scanner sync status
        self.emit_log(
            "INFO",
            "wms.scanner_sync status=nominal all_readers=synced",
            {"operation": "scanner_sync", "check.result": "PASS"},
        )
