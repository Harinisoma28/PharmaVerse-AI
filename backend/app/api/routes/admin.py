from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.routes.ai import fda_service
from app.core.config import settings
from app.core.security import require_roles
from app.database.connection import get_db
from app.models.batch import Batch
from app.models.drug import Drug
from app.models.qr_record import QRRecord
from app.models.rfid_record import RFIDRecord
from app.models.shipment import Shipment
from app.models.user import User


router = APIRouter(prefix="/api/admin", tags=["Admin"])


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@router.get("/dashboard/summary")
def admin_dashboard_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN")),
):
    users_by_role = dict(
        db.query(User.role, func.count(User.id)).group_by(User.role).all()
    )
    now = _utc_now_naive()

    # A query here also verifies the database connection used by this request.
    total_users = db.query(func.count(User.id)).scalar() or 0
    total_drugs = db.query(func.count(Drug.id)).scalar() or 0
    total_batches = db.query(func.count(Batch.id)).scalar() or 0
    expired_batches = (
        db.query(func.count(Batch.id))
        .filter(Batch.expiry_date < now.date())
        .scalar()
        or 0
    )
    inactive_qr = (
        db.query(func.count(QRRecord.id))
        .filter(func.upper(QRRecord.status) != "ACTIVE")
        .scalar()
        or 0
    )
    inactive_rfid = (
        db.query(func.count(RFIDRecord.id))
        .filter(func.upper(RFIDRecord.status) != "ACTIVE")
        .scalar()
        or 0
    )
    shipment_status_counts = dict(
        db.query(Shipment.status, func.count(Shipment.id))
        .group_by(Shipment.status)
        .all()
    )
    overdue_shipments = (
        db.query(func.count(Shipment.id))
        .filter(
            Shipment.status == "IN_TRANSIT",
            Shipment.expected_arrival.isnot(None),
            Shipment.expected_arrival < now,
        )
        .scalar()
        or 0
    )
    recent_shipments = (
        db.query(Shipment)
        .order_by(Shipment.created_at.desc())
        .limit(8)
        .all()
    )
    fda_summary = fda_service.live_summary()

    return {
        "counts": {
            "total_users": total_users,
            "active_users": (
                db.query(func.count(User.id)).filter(User.is_active.is_(True)).scalar()
                or 0
            ),
            "users_by_role": users_by_role,
            "total_drugs": total_drugs,
            "total_batches": total_batches,
            "expired_batches": expired_batches,
            "inactive_qr_records": inactive_qr,
            "inactive_rfid_records": inactive_rfid,
            "active_shipments": shipment_status_counts.get("IN_TRANSIT", 0),
            "delivered_shipments": shipment_status_counts.get("DELIVERED", 0),
            "created_shipments": shipment_status_counts.get("CREATED", 0),
            "overdue_in_transit_shipments": overdue_shipments,
        },
        "verification_history": {
            "persisted": False,
            "detail": "Verification results are not stored in the current database schema.",
        },
        "system_status": {
            "database": "operational",
            "fabric": "enabled" if settings.fabric_enabled else "disabled",
            "ai": "operational",
            "fda": {
                key: source["status"]
                for key, source in fda_summary["sources"].items()
            },
        },
        "fda_checked_at": fda_summary["checked_at"],
        "recent_activity": [
            {
                "shipment_id": shipment.shipment_id,
                "status": shipment.status,
                "source": shipment.source_location,
                "destination": shipment.destination_location,
                "created_at": shipment.created_at,
            }
            for shipment in recent_shipments
        ],
    }
