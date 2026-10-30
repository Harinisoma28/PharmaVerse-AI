from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.ai.models import ensure_utc


class _UTCTimestampMixin(BaseModel):
    """Normalize the ``timestamp`` field to timezone-aware UTC.

    Clients may send "Z"/offset timestamps or naive ones; mixing them made the
    correlation and delay logic raise ``TypeError`` (HTTP 500).
    """

    @field_validator("timestamp", check_fields=False)
    @classmethod
    def _timestamp_to_utc(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class AIReadingInput(_UTCTimestampMixin):
    timestamp: datetime
    temperature: float | None = None
    humidity: float | None = None
    latitude: float | None = None
    longitude: float | None = None
    location_name: str | None = None
    speed: float | None = None
    sensor_id: str = "api-sensor"
    rfid_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AIRoutePointInput(_UTCTimestampMixin):
    latitude: float
    longitude: float
    location_name: str
    timestamp: datetime


class AIRFIDEventInput(_UTCTimestampMixin):
    event_type: str
    location_name: str
    timestamp: datetime
    rfid_id: str | None = None
    expected_rfid_id: str | None = None
    qr_id: str | None = None
    product_id: str | None = None
    batch_id: str | None = None
    owner: str | None = None
    authorized: bool | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AIAnalysisRequest(BaseModel):
    shipment_id: str = Field(min_length=1, max_length=100)
    readings: list[AIReadingInput] = Field(default_factory=list)
    rfid_events: list[AIRFIDEventInput] = Field(default_factory=list)
    planned_route: list[AIRoutePointInput] = Field(default_factory=list)
    actual_rfid_id: str | None = None
    actual_qr_id: str | None = None
    actual_product_id: str | None = None
    actual_batch_id: str | None = None
    actual_owner: str | None = None
    expected_duration_hours: float | None = Field(default=None, gt=0)
    delay_tolerance_hours: float = Field(default=1.0, ge=0)
    route_threshold_km: float = Field(default=25.0, gt=0)


class AIBlockchainMetadata(BaseModel):
    status: str
    transaction_id: str | None = None
    evidence_hash: str


class AIAnalysisResponse(BaseModel):
    shipment_id: str
    anomalies: list[dict[str, Any]]
    correlations: list[dict[str, Any]]
    risk: dict[str, Any]
    counterfeit: dict[str, Any]
    alerts: list[dict[str, Any]]
    explanations: list[str]
    explainability: dict[str, Any]
    blockchain: AIBlockchainMetadata
    ml_assessment: dict[str, Any] | None = None
