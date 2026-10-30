from datetime import datetime

from backend.app.ai.anomaly_detector import AnomalyDetector
from backend.app.ai.explainability import ExplainabilityEngine
from backend.app.ai.models import IoTReading, StorageCondition, RiskScore


def test_explainability_lists_reasoning_for_high_risk_cases():
    reading = IoTReading(
        shipment_id="SHP-700",
        timestamp=datetime.utcnow(),
        temperature=12.0,
        humidity=75.0,
        latitude=12.1,
        longitude=77.2,
        location_name="Bengaluru",
        speed=90.0,
        sensor_id="sensor-700",
        rfid_id=None,
    )
    anomalies = AnomalyDetector().detect(reading, condition=StorageCondition(2.0, 8.0, 35.0, 65.0))
    risk = RiskScore(
        shipment_id="SHP-700",
        score=70.0,
        risk_level="high",
        drivers=["temperature deviation"],
        explanation=["temperature issue"],
        evidence_count=len(anomalies),
    )
    explanation = ExplainabilityEngine().explain(risk, anomalies)
    assert len(explanation) >= 1
    assert any("Temperature" in item for item in explanation)
