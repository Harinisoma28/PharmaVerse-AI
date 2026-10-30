from datetime import datetime

from backend.app.ai.anomaly_detector import AnomalyDetector
from backend.app.ai.models import IoTReading, StorageCondition
from backend.app.ai.risk_engine import RiskEngine


def test_risk_engine_scores_high_risk_cases():
    reading = IoTReading(
        shipment_id="SHP-500",
        timestamp=datetime.utcnow(),
        temperature=11.0,
        humidity=75.0,
        latitude=12.1,
        longitude=77.2,
        location_name="Bengaluru",
        speed=90.0,
        sensor_id="sensor-500",
        rfid_id=None,
    )
    anomalies = AnomalyDetector().detect(reading, condition=StorageCondition(2.0, 8.0, 35.0, 65.0))
    risk = RiskEngine().assess("SHP-500", anomalies)
    assert risk.score >= 45
    assert risk.risk_level in {"high", "critical"}
