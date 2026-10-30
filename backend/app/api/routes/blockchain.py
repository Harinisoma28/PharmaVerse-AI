from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.blockchain.fabric_client import (
    FabricAssetNotFoundError,
    FabricClient,
    FabricGatewayError,
    FabricUnavailableError,
)
from app.core.security import get_current_user
from app.core.security import require_roles
from app.database.connection import get_db
from app.models.user import User
from app.services.batch_lookup import find_batch_by_public_id
from app.schemas.blockchain import (
    BlockchainAIAlertWrite,
    BlockchainBatchWrite,
    BlockchainDrugWrite,
    BlockchainFlagWrite,
    BlockchainIdentityWrite,
    BlockchainIoTWrite,
    BlockchainReceiveWrite,
    BlockchainResponse,
    BlockchainShipWrite,
    BlockchainTransferWrite,
    BlockchainVerifyRequest,
)


router = APIRouter(
    prefix="/api/blockchain",
    tags=["Blockchain"],
)


def _fabric_error(exc: FabricUnavailableError | FabricGatewayError) -> HTTPException:
    return HTTPException(
        status_code=(
            status.HTTP_404_NOT_FOUND
            if isinstance(exc, FabricAssetNotFoundError)
            else status.HTTP_503_SERVICE_UNAVAILABLE
            if isinstance(exc, FabricUnavailableError)
            else status.HTTP_502_BAD_GATEWAY
        ),
        detail=str(exc),
    )


def _identity(user: User) -> str:
    return user.organization or user.username


def _persist_batch_transaction(db: Session, batch_id: str, result: object) -> None:
    if not isinstance(result, dict) or not result.get("transactionId"):
        return
    batch = find_batch_by_public_id(db, batch_id)
    if batch is None:
        return
    batch.last_fabric_transaction_id = str(result["transactionId"])
    db.commit()


def _write_error(exc: FabricUnavailableError | FabricGatewayError) -> HTTPException:
    return _fabric_error(exc)


@router.get("/drugs/{drug_id}", response_model=BlockchainResponse)
def get_drug(
    drug_id: str,
    current_user: User = Depends(get_current_user),
):
    try:
        return {"data": FabricClient().get_drug(drug_id)}
    except (FabricUnavailableError, FabricGatewayError) as exc:
        raise _fabric_error(exc) from exc


@router.get("/batches/{batch_id}", response_model=BlockchainResponse)
def get_batch(
    batch_id: str,
    current_user: User = Depends(get_current_user),
):
    try:
        return {"data": FabricClient().get_batch(batch_id)}
    except (FabricUnavailableError, FabricGatewayError) as exc:
        raise _fabric_error(exc) from exc


@router.get("/shipments/{shipment_id}", response_model=BlockchainResponse)
def get_shipment(
    shipment_id: str,
    current_user: User = Depends(get_current_user),
):
    try:
        return {"data": FabricClient().get_shipment(shipment_id)}
    except (FabricUnavailableError, FabricGatewayError) as exc:
        raise _fabric_error(exc) from exc


@router.get("/flags/{flag_id}", response_model=BlockchainResponse)
def get_flag(
    flag_id: str,
    current_user: User = Depends(get_current_user),
):
    try:
        return {"data": FabricClient().get_flag(flag_id)}
    except (FabricUnavailableError, FabricGatewayError) as exc:
        raise _fabric_error(exc) from exc


@router.get("/iot-events/{event_id}", response_model=BlockchainResponse)
def get_iot_event(
    event_id: str,
    current_user: User = Depends(get_current_user),
):
    try:
        return {"data": FabricClient().get_iot_event(event_id)}
    except (FabricUnavailableError, FabricGatewayError) as exc:
        raise _fabric_error(exc) from exc


@router.get("/ai-alerts/{alert_id}", response_model=BlockchainResponse)
def get_ai_alert(
    alert_id: str,
    current_user: User = Depends(get_current_user),
):
    try:
        return {"data": FabricClient().get_ai_alert(alert_id)}
    except (FabricUnavailableError, FabricGatewayError) as exc:
        raise _fabric_error(exc) from exc


@router.get("/batches/{batch_id}/history", response_model=BlockchainResponse)
def get_batch_history(
    batch_id: str,
    current_user: User = Depends(get_current_user),
):
    try:
        return {"data": FabricClient().get_batch_history(batch_id)}
    except (FabricUnavailableError, FabricGatewayError) as exc:
        raise _fabric_error(exc) from exc


@router.post("/verify-identity", response_model=BlockchainResponse)
def verify_identity(
    request: BlockchainVerifyRequest,
    current_user: User = Depends(get_current_user),
):
    try:
        return {
            "data": FabricClient().verify_identity(
                request.batch_id,
                request.qr_id,
                request.rfid_id,
            )
        }
    except (FabricUnavailableError, FabricGatewayError) as exc:
        raise _fabric_error(exc) from exc


@router.post("/writes/drugs", response_model=BlockchainResponse)
def register_drug(
    request: BlockchainDrugWrite,
    current_user: User = Depends(require_roles("ADMIN", "REGULATOR", "MANUFACTURER")),
):
    try:
        return {"data": FabricClient().register_drug(**request.model_dump())}
    except (FabricUnavailableError, FabricGatewayError) as exc:
        raise _write_error(exc) from exc


@router.post("/writes/batches", response_model=BlockchainResponse)
def create_batch(
    request: BlockchainBatchWrite,
    current_user: User = Depends(require_roles("ADMIN", "REGULATOR", "MANUFACTURER")),
):
    try:
        return {"data": FabricClient().create_batch(**request.model_dump())}
    except (FabricUnavailableError, FabricGatewayError) as exc:
        raise _write_error(exc) from exc


@router.post("/writes/identities", response_model=BlockchainResponse)
def assign_identity(
    request: BlockchainIdentityWrite,
    current_user: User = Depends(require_roles("ADMIN", "REGULATOR", "MANUFACTURER")),
    db: Session = Depends(get_db),
):
    try:
        result = FabricClient().assign_identity(**request.model_dump())
        _persist_batch_transaction(db, request.batch_id, result)
        return {"data": result}
    except (FabricUnavailableError, FabricGatewayError) as exc:
        raise _write_error(exc) from exc


@router.post("/writes/iot-events", response_model=BlockchainResponse)
def record_iot_event(
    request: BlockchainIoTWrite,
    current_user: User = Depends(require_roles("ADMIN", "REGULATOR")),
):
    try:
        result = request.model_dump()
        result["detectedBy"] = _identity(current_user)
        return {"data": FabricClient().record_iot_event(**{
            "batchId": result["batch_id"], "shipmentId": result["shipment_id"],
            "temperature": result["temperature"], "humidity": result["humidity"],
            "latitude": result["latitude"], "longitude": result["longitude"],
            "movement": result["movement"], "rfidId": result["rfid_id"],
        })}
    except (FabricUnavailableError, FabricGatewayError) as exc:
        raise _write_error(exc) from exc


@router.post("/writes/ai-alerts", response_model=BlockchainResponse)
def record_ai_alert(
    request: BlockchainAIAlertWrite,
    current_user: User = Depends(require_roles("ADMIN", "REGULATOR")),
):
    try:
        data = request.model_dump()
        return {"data": FabricClient().record_ai_alert(
            batchId=data["batch_id"], shipmentId=data["shipment_id"],
            alertType=data["alert_type"], riskScore=data["risk_score"],
            explanation=data["explanation"], detectedBy=_identity(current_user),
        )}
    except (FabricUnavailableError, FabricGatewayError) as exc:
        raise _write_error(exc) from exc


@router.post("/writes/flags", response_model=BlockchainResponse)
def flag_drug(
    request: BlockchainFlagWrite,
    current_user: User = Depends(require_roles("ADMIN", "REGULATOR")),
    db: Session = Depends(get_db),
):
    try:
        result = FabricClient().flag_drug(
            request.batch_id, request.reason, request.risk_level, _identity(current_user)
        )
        _persist_batch_transaction(db, request.batch_id, result)
        return {"data": result}
    except (FabricUnavailableError, FabricGatewayError) as exc:
        raise _write_error(exc) from exc


@router.post("/writes/shipments", response_model=BlockchainResponse)
def ship_drug(
    request: BlockchainShipWrite,
    current_user: User = Depends(require_roles(
        "ADMIN", "MANUFACTURER", "DISTRIBUTOR", "TRANSPORTER"
    )),
):
    try:
        data = request.model_dump()
        return {"data": FabricClient().ship_drug(
            shipmentId=data["shipment_id"], batchId=data["batch_id"],
            **{"from": data["from_location"], "to": data["to_location"],
               "transporter": _identity(current_user)}
        )}
    except (FabricUnavailableError, FabricGatewayError) as exc:
        raise _write_error(exc) from exc


@router.post("/writes/shipments/receive", response_model=BlockchainResponse)
def receive_drug(
    request: BlockchainReceiveWrite,
    current_user: User = Depends(require_roles(
        "ADMIN", "DISTRIBUTOR", "PHARMACY"
    )),
):
    try:
        return {"data": FabricClient().receive_drug(
            request.shipment_id, _identity(current_user)
        )}
    except (FabricUnavailableError, FabricGatewayError) as exc:
        raise _write_error(exc) from exc


@router.post("/writes/transfers", response_model=BlockchainResponse)
def transfer_drug(
    request: BlockchainTransferWrite,
    current_user: User = Depends(require_roles(
        "ADMIN", "MANUFACTURER", "DISTRIBUTOR", "PHARMACY"
    )),
    db: Session = Depends(get_db),
):
    try:
        result = FabricClient().transfer_drug(
            request.batch_id, _identity(current_user), request.to_owner
        )
        _persist_batch_transaction(db, request.batch_id, result)
        return {"data": result}
    except (FabricUnavailableError, FabricGatewayError) as exc:
        raise _write_error(exc) from exc
