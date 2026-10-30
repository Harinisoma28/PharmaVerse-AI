from __future__ import annotations

from typing import Iterable, List, Optional

from .models import AnomalyRecord, CorrelationRecord, RiskScore


class RiskEngine:
    FACTOR_WEIGHTS = {
        "environmental": 20,
        "route": 20,
        "delay": 15,
        "identity": 20,
        "ownership": 10,
        "blockchain": 10,
        "expiry": 5,
    }

    def assess(
        self,
        shipment_id: str,
        anomalies: Iterable[AnomalyRecord],
        correlations: Optional[Iterable[CorrelationRecord]] = None,
    ) -> RiskScore:
        anomaly_list = list(anomalies)
        active_factors = {item.factor for item in anomaly_list if item.factor in self.FACTOR_WEIGHTS}
        score = sum(self.FACTOR_WEIGHTS[factor] for factor in active_factors)
        correlation_list = list(correlations or [])
        correlation_bonus = sum(10 for item in correlation_list if len(item.event_types) > 1)
        score = min(100.0, float(score + min(20, correlation_bonus)))

        if score >= 75:
            risk_level = "critical"
        elif score >= 50:
            risk_level = "high"
        elif score >= 25:
            risk_level = "medium"
        else:
            risk_level = "low"

        drivers = sorted(
            {
                {
                    "environmental": "environmental deviation",
                    "route": "route deviation",
                    "delay": "shipment delay",
                    "identity": "identity inconsistency",
                    "ownership": "ownership inconsistency",
                    "blockchain": "blockchain verification unavailable",
                    "expiry": "expiry concern",
                }[factor]
                for factor in active_factors
            }
        )
        if correlation_bonus:
            drivers.append("temporally correlated events")
        if not drivers:
            drivers = ["no anomalies detected"]

        explanation = [
            f"Detected {len(anomaly_list)} evidence-backed anomaly(s).",
            f"Applied factor weights {sorted(active_factors) or ['none']} and a {min(20, correlation_bonus):.0f}-point correlation adjustment.",
            f"Aggregated risk score is {score:.1f}/100, classified as {risk_level}.",
        ]
        return RiskScore(
            shipment_id=shipment_id,
            score=score,
            risk_level=risk_level,
            drivers=drivers,
            explanation=explanation,
            evidence_count=len(anomaly_list),
            requires_human_review=score >= 50,
        )
