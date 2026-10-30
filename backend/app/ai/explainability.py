from __future__ import annotations

from typing import Iterable, List

from .models import AnomalyRecord, RiskScore


class ExplainabilityEngine:
    def explain(self, risk: RiskScore, anomalies: Iterable[AnomalyRecord]) -> List[str]:
        items = list(anomalies)
        if not items:
            return ["No anomalies were recorded; the risk score remains low because the shipment stayed within the expected monitoring thresholds."]

        reasons: List[str] = []
        for item in items:
            if item.type == "temperature_excursion":
                reasons.append(
                    f"Temperature excursion detected at sensor {item.sensor_id}: {item.message}"
                )
            elif item.type == "humidity_excursion":
                reasons.append(f"Humidity excursion was observed: {item.evidence}.")
            elif item.type == "route_deviation":
                reasons.append(f"Coordinates left the planned route corridor: {item.evidence}.")
            elif item.type == "shipment_delay":
                reasons.append(f"Projected arrival is late based on expected and actual duration: {item.evidence}.")
            elif item.type in {"rfid_missing", "rfid_mismatch", "rfid_duplicate"}:
                reasons.append(f"RFID chain-of-custody evidence is inconsistent: {item.evidence}.")
            elif item.type in {"qr_mismatch", "missing_identity", "ownership_inconsistency"}:
                reasons.append(f"Product identity/provenance evidence is inconsistent: {item.evidence}.")
        return reasons[:5]
