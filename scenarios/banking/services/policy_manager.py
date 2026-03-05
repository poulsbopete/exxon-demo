"""Policy Manager service — GCP us-central1-a. Policy admin, renewals, endorsements."""

from __future__ import annotations

import random
import time

from app.services.base_service import BaseService


class PolicyManagerService(BaseService):
    SERVICE_NAME = "policy-manager"

    def __init__(self, chaos_controller, otlp_client):
        super().__init__(chaos_controller, otlp_client)
        self._renewals_processed = 0
        self._last_summary = time.time()

    def generate_telemetry(self) -> None:
        active_channels = self.get_active_channels_for_service()
        for ch in active_channels:
            self.emit_fault_logs(ch)

        cascade_channels = self.get_cascade_channels_for_service()
        for ch in cascade_channels:
            self.emit_cascade_logs(ch)

        self._emit_renewal_processing()
        self._emit_endorsement_activity()

        if time.time() - self._last_summary > 10:
            self._emit_policy_summary()
            self._last_summary = time.time()

        active_policies = random.randint(2800000, 3200000)
        self.emit_metric("policy_manager.active_policies", float(active_policies), "policies")
        self.emit_metric("policy_manager.renewal_rate", round(random.uniform(92.0, 98.0), 1), "%")
        self.emit_metric("policy_manager.endorsement_queue", float(random.randint(10, 100)), "endorsements")

    def _emit_renewal_processing(self) -> None:
        self._renewals_processed += 1
        product = random.choice(["AUTO", "HOMEOWNERS", "RENTERS", "UMBRELLA"])
        premium = round(random.uniform(400, 3000), 2)
        self.emit_log(
            "INFO",
            f"[POLICY] renewal_processed product={product} premium=${premium} mvr_clear=true rating_complete=true status=RENEWED",
            {
                "operation": "renewal_processed",
                "policy.product": product,
                "policy.premium": premium,
                "policy.mvr_clear": True,
            },
        )

    def _emit_endorsement_activity(self) -> None:
        endorsement = random.choice([
            "ADD_VEHICLE", "REMOVE_DRIVER", "ADDRESS_CHANGE",
            "COVERAGE_INCREASE", "DEDUCTIBLE_CHANGE", "PCS_UPDATE",
        ])
        self.emit_log(
            "INFO",
            f"[POLICY] endorsement_applied type={endorsement} effective=IMMEDIATE premium_impact=+$12.40 status=APPLIED",
            {
                "operation": "endorsement_applied",
                "endorsement.type": endorsement,
                "endorsement.effective": "IMMEDIATE",
            },
        )

    def _emit_policy_summary(self) -> None:
        self.emit_log(
            "INFO",
            f"[POLICY] admin_summary renewals={self._renewals_processed} retention=95.2% scra_protected=847 status=NOMINAL",
            {
                "operation": "admin_summary",
                "admin.renewals": self._renewals_processed,
                "admin.retention_rate": 95.2,
            },
        )
