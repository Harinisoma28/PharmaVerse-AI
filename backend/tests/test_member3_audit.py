from datetime import datetime, timedelta, timezone

from backend.app.ai.correlation_engine import CorrelationEngine
from backend.app.ai.models import AnomalyRecord
from backend.app.simulation.manager import SimulationManager


def _anomaly(kind: str, timestamp: datetime, factor: str) -> AnomalyRecord:
    return AnomalyRecord(
        shipment_id="audit",
        sensor_id="audit-sensor",
        type=kind,
        severity="high",
        message=kind,
        timestamp=timestamp,
        factor=factor,
        evidence={"source": "audit"},
    )


def test_scenarios_expose_evidence_backed_results():
    manager = SimulationManager()
    normal = manager.run_scenario("normal")["analysis"]
    route = manager.run_scenario("route_deviation")["analysis"]
    delayed = manager.run_scenario("delayed_shipment")["analysis"]

    assert normal["risk"]["score"] == 0
    assert "route_deviation" in {item["type"] for item in route["anomalies"]}
    assert "shipment_delay" in {item["type"] for item in delayed["anomalies"]}
    assert route["anomalies"][0]["evidence"]["nearest_route_distance_km"] > 25


def test_correlation_window_changes_the_score():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    close = [
        _anomaly("temperature_excursion", start, "environmental"),
        _anomaly("route_deviation", start + timedelta(minutes=10), "route"),
        _anomaly("shipment_delay", start + timedelta(minutes=20), "delay"),
    ]
    distant = [
        _anomaly("temperature_excursion", start, "environmental"),
        _anomaly("route_deviation", start + timedelta(hours=2), "route"),
        _anomaly("shipment_delay", start + timedelta(hours=4), "delay"),
    ]
    engine = CorrelationEngine()
    close_records = engine.correlate(close, window_minutes=60)
    distant_records = engine.correlate(distant, window_minutes=60)

    assert any(len(record.event_types) == 3 for record in close_records)
    assert all(len(record.event_types) == 1 for record in distant_records)
