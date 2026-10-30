from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional, Sequence

from .alert_engine import AlertEngine
from .anomaly_detector import AnomalyDetector
from .correlation_engine import CorrelationEngine
from .counterfeit_detector import CounterfeitDetector
from .explainability import ExplainabilityEngine
from .models import (
    AIAnalysisResult,
    AnomalyRecord,
    IoTReading,
    StorageCondition,
    ensure_utc,
    evidence_hash,
)
from .risk_engine import RiskEngine
from ..simulation.models import RFIDEvent, RoutePoint
from ..ml.model import ML_DISCLAIMER, RiskModel


class AIService:
    def __init__(
        self,
        anomaly_detector: Optional[AnomalyDetector] = None,
        correlation_engine: Optional[CorrelationEngine] = None,
        risk_engine: Optional[RiskEngine] = None,
        counterfeit_detector: Optional[CounterfeitDetector] = None,
        explainability_engine: Optional[ExplainabilityEngine] = None,
        alert_engine: Optional[AlertEngine] = None,
    ):
        self.anomaly_detector = anomaly_detector or AnomalyDetector()
        self.correlation_engine = correlation_engine or CorrelationEngine()
        self.risk_engine = risk_engine or RiskEngine()
        self.counterfeit_detector = counterfeit_detector or CounterfeitDetector()
        self.explainability_engine = explainability_engine or ExplainabilityEngine()
        self.alert_engine = alert_engine or AlertEngine()

    def analyze_readings(
        self,
        shipment_id: str,
        readings: Iterable[IoTReading],
        storage_condition: Optional[StorageCondition] = None,
        expected_rfid_id: Optional[str] = None,
        actual_rfid_id: Optional[str] = None,
        planned_route: Optional[Sequence[RoutePoint]] = None,
        expected_duration_hours: Optional[float] = None,
        delay_tolerance_hours: float = 1.0,
        route_threshold_km: float = 25.0,
        expected_qr_id: Optional[str] = None,
        actual_qr_id: Optional[str] = None,
        expected_product_id: Optional[str] = None,
        actual_product_id: Optional[str] = None,
        expected_batch_id: Optional[str] = None,
        actual_batch_id: Optional[str] = None,
        expected_owner: Optional[str] = None,
        actual_owner: Optional[str] = None,
        expiry_date: Optional[datetime] = None,
        rfid_events: Optional[Iterable[RFIDEvent]] = None,
    ) -> Dict[str, Any]:
        readings_list = list(readings)
        anomalies = self.anomaly_detector.detect_many(
            readings_list,
            condition=storage_condition,
            planned_route=planned_route,
            route_threshold_km=route_threshold_km,
            expected_duration_hours=expected_duration_hours,
            delay_tolerance_hours=delay_tolerance_hours,
        )
        events = list(rfid_events or [])
        if events:
            observed_ids = [event.rfid_id for event in events]
            if expected_rfid_id and any(item != expected_rfid_id for item in observed_ids):
                anomalies.append(
                    AnomalyRecord(
                        shipment_id=shipment_id,
                        sensor_id="rfid-gateway",
                        type="rfid_mismatch",
                        severity="high",
                        message="At least one RFID scan differs from the expected shipment RFID.",
                        timestamp=events[-1].timestamp,
                        factor="identity",
                        evidence={"expected_rfid_id": expected_rfid_id, "observed_rfid_ids": observed_ids},
                    )
                )
            event_keys = [(event.rfid_id, event.location_name, event.timestamp) for event in events]
            if len(event_keys) != len(set(event_keys)):
                anomalies.append(
                    AnomalyRecord(
                        shipment_id=shipment_id,
                        sensor_id="rfid-gateway",
                        type="rfid_duplicate",
                        severity="medium",
                        message="Duplicate RFID activity was observed.",
                        timestamp=events[-1].timestamp,
                        factor="identity",
                        evidence={"observed_rfid_ids": observed_ids},
                    )
                )
            if any(event.authorized is False for event in events):
                anomalies.append(
                    AnomalyRecord(
                        shipment_id=shipment_id,
                        sensor_id="rfid-gateway",
                        type="ownership_inconsistency",
                        severity="high",
                        message="An RFID transfer was not authorized.",
                        timestamp=events[-1].timestamp,
                        factor="ownership",
                        evidence={"unauthorized_events": [event.model_dump(mode="json") for event in events if event.authorized is False]},
                    )
                )

        if expected_qr_id and actual_qr_id and expected_qr_id != actual_qr_id:
            anomalies.append(
                AnomalyRecord(
                    shipment_id=shipment_id,
                    sensor_id="identity-gateway",
                    type="qr_mismatch",
                    severity="high",
                    message="QR identity differs from the expected product record.",
                    factor="identity",
                    evidence={"expected_qr_id": expected_qr_id, "actual_qr_id": actual_qr_id},
                )
            )
        if expected_rfid_id and actual_rfid_id and expected_rfid_id != actual_rfid_id and not any(
            item.type == "rfid_mismatch" for item in anomalies
        ):
            anomalies.append(
                AnomalyRecord(
                    shipment_id=shipment_id,
                    sensor_id="identity-gateway",
                    type="rfid_mismatch",
                    severity="high",
                    message="RFID identity differs from the expected shipment record.",
                    factor="identity",
                    evidence={"expected_rfid_id": expected_rfid_id, "actual_rfid_id": actual_rfid_id},
                )
            )
        if expected_owner and actual_owner and expected_owner != actual_owner:
            anomalies.append(
                AnomalyRecord(
                    shipment_id=shipment_id,
                    sensor_id="identity-gateway",
                    type="ownership_inconsistency",
                    severity="high",
                    message="Ownership differs from the expected authorized owner.",
                    factor="ownership",
                    evidence={"expected_owner": expected_owner, "actual_owner": actual_owner},
                )
            )
        if not all((expected_rfid_id, expected_qr_id, expected_product_id, expected_batch_id)):
            anomalies.append(
                AnomalyRecord(
                    shipment_id=shipment_id,
                    sensor_id="identity-gateway",
                    type="missing_identity",
                    severity="medium",
                    message="One or more identity fields are unavailable.",
                    factor="identity",
                    evidence={
                        "expected_rfid_id": expected_rfid_id,
                        "expected_qr_id": expected_qr_id,
                        "expected_product_id": expected_product_id,
                        "expected_batch_id": expected_batch_id,
                    },
                )
            )
        if expiry_date and ensure_utc(expiry_date) < datetime.now(timezone.utc):
                anomalies.append(
                    AnomalyRecord(
                        shipment_id=shipment_id,
                        sensor_id="identity-gateway",
                        type="expired_product",
                        severity="high",
                        message="Product expiry date has passed.",
                        factor="expiry",
                        evidence={"expiry_date": expiry_date},
                    )
                )
        correlations = self.correlation_engine.correlate(anomalies)
        risk = self.risk_engine.assess(shipment_id, anomalies, correlations)
        counterfeit = self.counterfeit_detector.assess(
            shipment_id,
            anomalies,
            expected_rfid_id,
            actual_rfid_id,
            expected_qr_id,
            actual_qr_id,
            expected_product_id,
            actual_product_id,
            expected_batch_id,
            actual_batch_id,
            expected_owner,
            actual_owner,
            expiry_date,
        )
        alerts = self.alert_engine.build_alerts(shipment_id, risk, counterfeit, anomalies)
        explanations = self.explainability_engine.explain(risk, anomalies)
        evidence = {
            "shipment_id": shipment_id,
            "anomalies": [item.model_dump(mode="json") for item in anomalies],
            "correlations": [item.model_dump(mode="json") for item in correlations],
        }
        result = AIAnalysisResult(
            shipment_id=shipment_id,
            anomalies=anomalies,
            correlations=correlations,
            risk=risk,
            counterfeit=counterfeit,
            alerts=alerts,
        )
        ml_model = RiskModel()
        ml_prediction = ml_model.predict(ml_model.features_from_analysis({
            "anomalies": [item.model_dump(mode="json") for item in anomalies],
        }))
        return {
            "shipment_id": result.shipment_id,
            "anomalies": [item.model_dump(mode="json") for item in result.anomalies],
            "correlations": [item.model_dump(mode="json") for item in result.correlations],
            "risk": result.risk.model_dump(mode="json"),
            "counterfeit": result.counterfeit.model_dump(mode="json"),
            "alerts": [item.model_dump(mode="json") for item in result.alerts],
            "explanations": explanations,
            "explainability": {
                "what_happened": explanations,
                "why_suspicious": result.risk.drivers,
                "evidence": evidence,
                "risk_score": result.risk.score,
                "recommended_action": [item for alert in alerts for item in alert.recommendations],
                "requires_human_review": result.risk.requires_human_review or counterfeit.is_counterfeit_risk,
            },
            "blockchain": {
                "status": "BLOCKCHAIN_UNAVAILABLE",
                "transaction_id": None,
                "evidence_hash": evidence_hash(evidence),
            },
            "ml_assessment": {
                "available": ml_prediction.available,
                "probability": ml_prediction.probability,
                "label": ml_prediction.label,
                "reason": ml_prediction.reason,
                "disclaimer": ML_DISCLAIMER,
            },
        }
