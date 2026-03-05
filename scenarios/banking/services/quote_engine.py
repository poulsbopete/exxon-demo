"""Quote Engine service — Azure eastus-1. Insurance rating, underwriting, VA loans."""

from __future__ import annotations

import random
import time

from app.services.base_service import BaseService


class QuoteEngineService(BaseService):
    SERVICE_NAME = "quote-engine"

    def __init__(self, chaos_controller, otlp_client):
        super().__init__(chaos_controller, otlp_client)
        self._quotes_generated = 0
        self._last_summary = time.time()

    def generate_telemetry(self) -> None:
        active_channels = self.get_active_channels_for_service()
        for ch in active_channels:
            self.emit_fault_logs(ch)

        cascade_channels = self.get_cascade_channels_for_service()
        for ch in cascade_channels:
            self.emit_cascade_logs(ch)

        self._emit_quote_generation()
        self._emit_va_loan_status()

        if time.time() - self._last_summary > 10:
            self._emit_quote_summary()
            self._last_summary = time.time()

        latency = round(random.uniform(200, 800), 1) if not active_channels else round(random.uniform(3000, 15000), 1)
        self.emit_metric("quote_engine.response_time_ms", latency, "ms")
        self.emit_metric("quote_engine.quotes_per_hour", float(random.randint(400, 1200)), "quotes/hr")
        self.emit_metric("quote_engine.bind_rate", round(random.uniform(28, 45), 1), "%")

    def _emit_quote_generation(self) -> None:
        self._quotes_generated += 1
        product = random.choice(["AUTO", "HOMEOWNERS", "RENTERS", "UMBRELLA", "VA_LOAN"])
        premium = round(random.uniform(200, 4000), 2)
        self.emit_log(
            "INFO",
            f"[UW] quote_generated product={product} premium=${premium} rules_evaluated=247 tier=PREFERRED status=QUOTED",
            {
                "operation": "quote_generated",
                "quote.product": product,
                "quote.premium": premium,
                "quote.tier": "PREFERRED",
            },
        )

    def _emit_va_loan_status(self) -> None:
        rate = round(random.uniform(5.5, 7.0), 3)
        amount = random.randint(200000, 600000)
        self.emit_log(
            "INFO",
            f"[UW] va_loan_prequal rate={rate}% amount=${amount} coe_valid=true dti=28% status=PRE_APPROVED",
            {
                "operation": "va_loan_prequal",
                "loan.rate": rate,
                "loan.amount": amount,
                "loan.coe_valid": True,
            },
        )

    def _emit_quote_summary(self) -> None:
        self.emit_log(
            "INFO",
            f"[UW] engine_summary quotes={self._quotes_generated} bind_rate=34% avg_premium=$1,842 military_discount_applied=92% status=NOMINAL",
            {
                "operation": "engine_summary",
                "engine.quotes": self._quotes_generated,
                "engine.bind_rate": 34,
            },
        )
