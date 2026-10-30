from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import get_current_user, require_roles
from app.database.connection import get_db
from app.models.shipment import Shipment
from app.models.shipment_tracking_event import ShipmentTrackingEvent
from app.models.user import User
from app.schemas.shipment import ShipmentCreate, ShipmentResponse, ShipmentTransfer
from app.services.batch_lookup import get_batch_or_404


router = APIRouter(
    prefix="/api/shipments",
    tags=["Shipments"],
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _add_tracking_event(
    db: Session,
    shipment: Shipment,
    *,
    event_type: str,
    status_value: str,
    location_name: str | None,
    event_time: datetime,
    expected_time: datetime | None = None,
    description: str | None = None,
) -> None:
    last_sequence = (
        db.query(func.max(ShipmentTrackingEvent.sequence_number))
        .filter(ShipmentTrackingEvent.shipment_id == getattr(shipment, "id", None))
        .scalar()
        or 0
    )
    db.add(
        ShipmentTrackingEvent(
            shipment_id=shipment.id,
            event_type=event_type,
            status=status_value,
            location_name=location_name,
            latitude=(
                getattr(shipment, "current_latitude", None)
                if event_type == "CHECKPOINT"
                else None
            ),
            longitude=(
                getattr(shipment, "current_longitude", None)
                if event_type == "CHECKPOINT"
                else None
            ),
            event_time=_as_utc(event_time),
            expected_time=_as_utc(expected_time),
            description=description,
            sequence_number=last_sequence + 1,
        )
    )


def _get_shipment_or_404(shipment_id: str, db: Session) -> Shipment:
    shipment = db.query(Shipment).filter(
        Shipment.shipment_id == shipment_id.strip()
    ).first()

    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shipment not found",
        )

    return shipment


@router.post(
    "",
    response_model=ShipmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_shipment(
    shipment_data: ShipmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("ADMIN", "REGULATOR", "MANUFACTURER")
    ),
):
    # shipment_data.batch_id is the *public* batch identifier (Batch.batch_id);
    # the shipment stores the batch's internal primary key (Batch.id).
    batch = get_batch_or_404(db, shipment_data.batch_id)

    existing_shipment = db.query(Shipment).filter(
        Shipment.shipment_id == shipment_data.shipment_id
    ).first()

    if existing_shipment:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Shipment ID already exists",
        )

    if (
        shipment_data.expected_departure
        and shipment_data.expected_arrival
        and shipment_data.expected_arrival <= shipment_data.expected_departure
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Expected arrival must be after expected departure",
        )

    shipment = Shipment(
        shipment_id=shipment_data.shipment_id,
        batch_id=batch.id,
        source_location=shipment_data.source,
        destination_location=shipment_data.destination,
        current_owner=shipment_data.current_owner,
        status=shipment_data.status,
        expected_departure=shipment_data.expected_departure,
        expected_arrival=shipment_data.expected_arrival,
        expected_latitude=shipment_data.expected_latitude,
        expected_longitude=shipment_data.expected_longitude,
    )

    db.add(shipment)
    db.flush()
    _add_tracking_event(
        db,
        shipment,
        event_type="CREATED",
        status_value="CREATED",
        location_name=getattr(shipment, "source_location", None),
        event_time=datetime.now(timezone.utc),
        expected_time=shipment.expected_departure,
        description="Shipment created.",
    )
    db.commit()
    db.refresh(shipment)

    return shipment


@router.get(
    "",
    response_model=list[ShipmentResponse],
)
def list_shipments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(Shipment).order_by(
        Shipment.created_at.desc()
    ).all()


@router.get(
    "/{shipment_id}",
    response_model=ShipmentResponse,
)
def get_shipment(
    shipment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _get_shipment_or_404(shipment_id, db)


@router.get("/{shipment_id}/tracking")
def get_shipment_tracking(
    shipment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    shipment = _get_shipment_or_404(shipment_id, db)
    events = (
        db.query(ShipmentTrackingEvent)
        .filter(ShipmentTrackingEvent.shipment_id == shipment.id)
        .order_by(
            ShipmentTrackingEvent.sequence_number,
            ShipmentTrackingEvent.event_time,
        )
        .all()
    )
    return {
        "shipment_id": shipment.shipment_id,
        "batch_id": shipment.batch.batch_id,
        "events": events,
    }


@router.post(
    "/{shipment_id}/depart",
    response_model=ShipmentResponse,
)
def depart_shipment(
    shipment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("ADMIN", "MANUFACTURER", "DISTRIBUTOR", "TRANSPORTER")
    ),
):
    shipment = _get_shipment_or_404(shipment_id, db)

    if shipment.status != "CREATED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Only shipments in CREATED status can depart "
                f"(current status: {shipment.status})"
            ),
        )

    shipment.status = "IN_TRANSIT"
    shipment.actual_departure = _utc_now()
    _add_tracking_event(
        db,
        shipment,
        event_type="DEPARTED",
        status_value="IN_TRANSIT",
        location_name=getattr(shipment, "source_location", None),
        event_time=datetime.now(timezone.utc),
        expected_time=getattr(shipment, "expected_departure", None),
        description="Shipment departed from the source.",
    )
    db.commit()
    db.refresh(shipment)

    return shipment


@router.post(
    "/{shipment_id}/receive",
    response_model=ShipmentResponse,
)
def receive_shipment(
    shipment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("ADMIN", "DISTRIBUTOR", "PHARMACY")
    ),
):
    shipment = _get_shipment_or_404(shipment_id, db)

    if shipment.status != "IN_TRANSIT":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only shipments in transit can be received",
        )

    shipment.status = "DELIVERED"
    shipment.actual_arrival = _utc_now()
    _add_tracking_event(
        db,
        shipment,
        event_type="DELIVERED",
        status_value="DELIVERED",
        location_name=getattr(shipment, "destination_location", None),
        event_time=datetime.now(timezone.utc),
        expected_time=getattr(shipment, "expected_arrival", None),
        description="Shipment received at its destination.",
    )
    db.commit()
    db.refresh(shipment)

    return shipment


def _normalize_party(value: str | None) -> str:
    return (value or "").strip().casefold()


def _is_current_owner(user: User, shipment: Shipment) -> bool:
    """True when the user acts for the shipment's current owner.

    ``Shipment.current_owner`` is a free-text party name, so a user is the
    owner when it equals their organization or their username
    (case-insensitive).  A shipment with no recorded owner has no owner who
    could authorize a hand-over.
    """
    owner = _normalize_party(shipment.current_owner)
    if not owner:
        return False
    return owner in {
        _normalize_party(getattr(user, "organization", None)),
        _normalize_party(getattr(user, "username", None)),
    } - {""}


@router.post(
    "/{shipment_id}/transfer",
    response_model=ShipmentResponse,
)
def transfer_shipment(
    shipment_id: str,
    transfer_data: ShipmentTransfer,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("ADMIN", "MANUFACTURER", "DISTRIBUTOR", "PHARMACY")
    ),
):
    shipment = _get_shipment_or_404(shipment_id, db)
    new_owner = transfer_data.new_owner.strip()

    if not new_owner:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New owner cannot be empty",
        )

    # Only the current owner (or an ADMIN) may hand a shipment over.  Without
    # this any authenticated user could reassign custody of any shipment.
    if current_user.role != "ADMIN" and not _is_current_owner(
        current_user, shipment
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the current owner or an ADMIN can transfer this shipment",
        )

    if _normalize_party(new_owner) == _normalize_party(shipment.current_owner):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New owner is already the current owner",
        )

    shipment.current_owner = new_owner
    _add_tracking_event(
        db,
        shipment,
        event_type="TRANSFERRED",
        status_value=shipment.status,
        location_name=None,
        event_time=datetime.now(timezone.utc),
        description=f"Shipment custody transferred to {new_owner}.",
    )
    db.commit()
    db.refresh(shipment)

    return shipment
