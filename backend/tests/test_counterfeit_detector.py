from datetime import datetime

from backend.app.ai.anomaly_detector import AnomalyDetector
from backend.app.ai.counterfeit_detector import CounterfeitDetector
from backend.app.ai.models import IoTReading, StorageCondition


def test_counterfeit_detector_reports_mismatch_risk():
    reading = IoTReading(
        shipment_id="SHP-600",
        timestamp=datetime.utcnow(),
        temperature=10.0,
        humidity=60.0,
        latitude=12.1,
        longitude=77.2,
        location_name="Bengaluru",
        speed=95.0,
        sensor_id="sensor-600",
        rfid_id="RFID-ALT",
    )
    anomalies = AnomalyDetector().detect(reading, condition=StorageCondition(2.0, 8.0, 35.0, 65.0))
    assessment = CounterfeitDetector().assess("SHP-600", anomalies, expected_rfid_id="RFID-PRIMARY", actual_rfid_id="RFID-ALT")
    assert assessment.is_counterfeit_risk is True
    assert assessment.risk_level in {"medium", "high", "critical"}
