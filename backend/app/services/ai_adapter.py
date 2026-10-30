from __future__ import annotations

from datetime import datetime, time, timezone
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.ai.service import AIService
from app.ai.models import IoTReading, StorageCondition
from app.models.batch import Batch
from app.models.qr_record import QRRecord
from app.models.rfid_record import RFIDRecord
from app.models.shipment import Shipment
from app.schemas.ai import AIAnalysisRequest
from app.simulation.models import RFIDEvent, RoutePoint


class AIAdapter:
    """Maps operational PostgreSQL data and request telemetry to AI inputs."""

    def __init__(self, ai_service: AIService | None = None):
        self.ai_service = ai_service or AIService()

    def analyze(
        self,
        request: AIAnalysisRequest,
        db: Session,
    ) -> dict:
        shipment = (
            db.query(Shipment)
            .filter(Shipment.shipment_id == request.shipment_id)
            .first()
        )
        if shipment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Shipment not found",
            )

        batch = db.query(Batch).filter(Batch.id == shipment.batch_id).first()
        if batch is None or batch.drug is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Shipment batch or drug not found",
            )

        qr = (
            db.query(QRRecord)
            .filter(QRRecord.batch_id == batch.id, QRRecord.status == "ACTIVE")
            .order_by(QRRecord.created_at.desc())
            .first()
        )
        rfid = (
            db.query(RFIDRecord)
            .filter(RFIDRecord.batch_id == batch.id, RFIDRecord.status == "ACTIVE")
            .order_by(RFIDRecord.created_at.desc())
            .first()
        )

        condition = self._storage_condition(batch.drug)
        expected_duration = request.expected_duration_hours
        if expected_duration is None and shipment.expected_departure and shipment.expected_arrival:
            expected_duration = (
                shipment.expected_arrival - shipment.expected_departure
            ).total_seconds() / 3600

        actual_rfid_id = request.actual_rfid_id or (rfid.rfid_id if rfid else None)
        actual_qr_id = request.actual_qr_id or (qr.qr_id if qr else None)
        actual_batch_id = request.actual_batch_id or batch.batch_id
        actual_product_id = request.actual_product_id or batch.drug.drug_id
        actual_owner = request.actual_owner or shipment.current_owner

        return self.ai_service.analyze_readings(
            shipment_id=shipment.shipment_id,
            readings=[
                IoTReading(
                    shipment_id=shipment.shipment_id,
                    **reading.model_dump(),
                )
                for reading in request.readings
            ],
            storage_condition=condition,
            expected_rfid_id=rfid.rfid_id if rfid else None,
            actual_rfid_id=actual_rfid_id,
            planned_route=[
                RoutePoint(**point.model_dump())
                for point in request.planned_route
            ],
            expected_duration_hours=expected_duration,
            delay_tolerance_hours=request.delay_tolerance_hours,
            route_threshold_km=request.route_threshold_km,
            expected_qr_id=qr.qr_id if qr else None,
            actual_qr_id=actual_qr_id,
            expected_product_id=batch.drug.drug_id,
            actual_product_id=actual_product_id,
            expected_batch_id=batch.batch_id,
            actual_batch_id=actual_batch_id,
            expected_owner=shipment.current_owner,
            actual_owner=actual_owner,
            expiry_date=datetime.combine(
                batch.expiry_date,
                time.min,
                tzinfo=timezone.utc,
            ),
            rfid_events=[
                RFIDEvent(
                    shipment_id=shipment.shipment_id,
                    **event.model_dump(),
                )
                for event in request.rfid_events
            ],
        )

    @staticmethod
    def _storage_condition(drug) -> StorageCondition | None:
        values = (
            drug.storage_min_temp,
            drug.storage_max_temp,
            drug.storage_min_humidity,
            drug.storage_max_humidity,
        )
        if any(value is None for value in values):
            return None
        return StorageCondition(
            minimum_temperature=drug.storage_min_temp,
            maximum_temperature=drug.storage_max_temp,
            minimum_humidity=drug.storage_min_humidity,
            maximum_humidity=drug.storage_max_humidity,
        )
