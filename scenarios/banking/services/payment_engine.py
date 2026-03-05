"""Payment Engine service — AWS us-east-1c. ACH, wire, P2P, bill pay processing."""

from __future__ import annotations

import random
import time

from app.services.base_service import BaseService


class PaymentEngineService(BaseService):
    SERVICE_NAME = "payment-engine"

    def __init__(self, chaos_controller, otlp_client):
        super().__init__(chaos_controller, otlp_client)
        self._transaction_count = 0
        self._last_summary = time.time()

    def generate_telemetry(self) -> None:
        active_channels = self.get_active_channels_for_service()
        for ch in active_channels:
            self.emit_fault_logs(ch)

        cascade_channels = self.get_cascade_channels_for_service()
        for ch in cascade_channels:
            self.emit_cascade_logs(ch)

        self._emit_transaction()
        self._emit_ach_batch_status()

        if time.time() - self._last_summary > 10:
            self._emit_payment_summary()
            self._last_summary = time.time()

        tps = round(random.uniform(120, 450), 1) if not active_channels else round(random.uniform(20, 80), 1)
        self.emit_metric("payment_engine.transactions_per_sec", tps, "txn/s")
        self.emit_metric("payment_engine.ach_queue_depth", float(random.randint(100, 2000)), "entries")
        self.emit_metric("payment_engine.auth_success_rate", round(random.uniform(98.5, 99.9), 2), "%")

    def _emit_transaction(self) -> None:
        self._transaction_count += 1
        txn_type = random.choice(["ACH_CREDIT", "ACH_DEBIT", "WIRE_DOM", "WIRE_INTL", "CARD_AUTH", "BILLPAY", "P2P"])
        amount = round(random.uniform(10, 5000), 2)
        self.emit_log(
            "INFO",
            f"[PAY] transaction_processed type={txn_type} amount=${amount} ofac_clear=true status=SETTLED",
            {
                "operation": "transaction_processed",
                "txn.type": txn_type,
                "txn.amount": amount,
                "txn.ofac_clear": True,
                "txn.status": "SETTLED",
            },
        )

    def _emit_ach_batch_status(self) -> None:
        entries = random.randint(500, 5000)
        amount = round(random.uniform(100000, 5000000), 2)
        self.emit_log(
            "INFO",
            f"[PAY] ach_batch_status entries={entries} total_amount=${amount} nacha_valid=true window=FED_06ET status=PROCESSING",
            {
                "operation": "ach_batch_status",
                "ach.entries": entries,
                "ach.total_amount": amount,
                "ach.nacha_valid": True,
            },
        )

    def _emit_payment_summary(self) -> None:
        self.emit_log(
            "INFO",
            f"[PAY] engine_summary total_txns={self._transaction_count} success_rate=99.7% avg_latency_ms=45 status=NOMINAL",
            {
                "operation": "engine_summary",
                "engine.total_txns": self._transaction_count,
                "engine.success_rate": 99.7,
            },
        )
