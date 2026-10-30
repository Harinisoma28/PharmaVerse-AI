from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Iterable, List

from .models import AnomalyRecord, CorrelationRecord, ensure_utc

_EARLIEST = datetime.min.replace(tzinfo=timezone.utc)


class CorrelationEngine:
    def correlate(self, anomalies: Iterable[AnomalyRecord], window_minutes: int = 60) -> List[CorrelationRecord]:
        by_shipment: dict[str, list[AnomalyRecord]] = defaultdict(list)
        for anomaly in anomalies:
            by_shipment[anomaly.shipment_id].append(anomaly)

        records: List[CorrelationRecord] = []
        for shipment_id, shipment_anomalies in by_shipment.items():
            ordered = sorted(
                shipment_anomalies,
                key=lambda item: ensure_utc(item.timestamp) if item.timestamp else _EARLIEST,
            )
            groups: list[list[AnomalyRecord]] = []
            for anomaly in ordered:
                if not groups or anomaly.timestamp is None or groups[-1][-1].timestamp is None:
                    groups.append([anomaly])
                elif ensure_utc(anomaly.timestamp) - ensure_utc(groups[-1][0].timestamp) <= timedelta(minutes=window_minutes):
                    groups[-1].append(anomaly)
                else:
                    groups.append([anomaly])

            for group in groups:
                types = sorted({item.type for item in group})
                if not types:
                    continue
                summary = "A single dominant anomaly is present."
                if len(types) > 1:
                    summary = "Multiple evidence-backed anomalies occurred within the correlation window."
                if {"temperature_excursion", "route_deviation", "shipment_delay"}.issubset(types):
                    summary = "Environmental, route, and delay evidence are temporally correlated."
                if {"rfid_mismatch", "qr_mismatch", "ownership_inconsistency"}.issubset(types):
                    summary = "Identity and ownership evidence are temporally correlated."

                confidence = min(0.95, 0.45 + len(group) * 0.1)
                records.append(
                    CorrelationRecord(
                        shipment_id=shipment_id,
                        event_types=types,
                        confidence=round(confidence, 2),
                        summary=summary,
                        evidence={
                            "count": len(group),
                            "types": types,
                            "window_minutes": window_minutes,
                            "start": group[0].timestamp,
                            "end": group[-1].timestamp,
                        },
                    )
                )
        return records
