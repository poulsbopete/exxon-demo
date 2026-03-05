"""Payment Processor service — Azure eastus-1. In-app purchases, virtual currency, and ledger management."""

from __future__ import annotations

import random
import time

from app.services.base_service import BaseService


class PaymentProcessorService(BaseService):
    SERVICE_NAME = "payment-processor"

    def __init__(self, chaos_controller, otlp_client):
        super().__init__(chaos_controller, otlp_client)
        self._transactions = 0
        self._last_ledger_report = time.time()
        self._providers = ["stripe", "paypal", "apple_iap", "google_play"]
        self._currencies = ["USD", "EUR", "GBP", "JPY"]

    def generate_telemetry(self) -> None:
        # ── Fault injection ────────────────────────────────────
        active_channels = self.get_active_channels_for_service()
        for ch in active_channels:
            self.emit_fault_logs(ch)

        cascade_channels = self.get_cascade_channels_for_service()
        for ch in cascade_channels:
            self.emit_cascade_logs(ch)

        # ── Normal telemetry ───────────────────────────────────
        self._emit_purchase_processed()
        self._emit_ledger_balance()

        if time.time() - self._last_ledger_report > 10:
            self._emit_revenue_summary()
            self._last_ledger_report = time.time()

        # Metrics
        txn_latency = round(random.uniform(80.0, 300.0), 1) if not active_channels else round(random.uniform(1000.0, 10000.0), 1)
        self.emit_metric("payment.transaction_latency_ms", txn_latency, "ms")
        self.emit_metric("payment.transactions_total", float(self._transactions), "txns")
        failure_rate = round(random.uniform(0.1, 1.5), 2) if not active_channels else round(random.uniform(5.0, 25.0), 2)
        self.emit_metric("payment.failure_rate", failure_rate, "%")

    def _emit_purchase_processed(self) -> None:
        self._transactions += 1
        provider = random.choice(self._providers)
        amount = round(random.uniform(0.99, 99.99), 2)
        currency = random.choice(self._currencies)
        item = random.choice(["battle-pass", "skin-legendary", "currency-pack-lg", "loot-box-10x", "emote-rare"])
        player_id = f"PLR-{random.randint(100000, 999999)}"
        self.emit_log(
            "INFO",
            f"[IAP] purchase_ok player={player_id} item={item} amount={amount}{currency} provider={provider} receipt=VALID",
            {
                "operation": "purchase_processed",
                "payment.provider": provider,
                "payment.amount": amount,
                "payment.currency": currency,
                "payment.item": item,
                "payment.player_id": player_id,
                "payment.status": "COMPLETED",
            },
        )

    def _emit_ledger_balance(self) -> None:
        player_id = f"PLR-{random.randint(100000, 999999)}"
        virtual_currency = random.choice(["gems", "coins", "credits", "tokens"])
        balance = random.randint(100, 100000)
        self.emit_log(
            "INFO",
            f"[IAP] ledger_check player={player_id} balance={balance} currency={virtual_currency} reconciled=true delta=0",
            {
                "operation": "ledger_check",
                "ledger.player_id": player_id,
                "ledger.currency": virtual_currency,
                "ledger.balance": balance,
                "ledger.status": "RECONCILED",
            },
        )

    def _emit_revenue_summary(self) -> None:
        revenue = round(self._transactions * random.uniform(3.0, 12.0), 2)
        self.emit_log(
            "INFO",
            f"[IAP] summary txn_count={self._transactions} gross_revenue={revenue} failure_rate=0.8% providers=4/4",
            {
                "operation": "revenue_summary",
                "summary.transactions": self._transactions,
                "summary.estimated_revenue": revenue,
            },
        )
