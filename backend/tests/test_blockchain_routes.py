from types import SimpleNamespace

import httpx
from fastapi.testclient import TestClient

from app.api.routes import blockchain as blockchain_routes
from app.blockchain.fabric_client import (
    FabricAssetNotFoundError,
    FabricClient,
    FabricGatewayError,
    FabricUnavailableError,
)
from app.core.config import settings
from app.core.security import get_current_user
from app.database.connection import get_db
from app.main import app


client = TestClient(app)


def user(role="VIEWER"):
    return lambda: SimpleNamespace(role=role, is_active=True)


def teardown_function():
    app.dependency_overrides.clear()


def test_blockchain_requires_authentication():
    response = client.get("/api/blockchain/drugs/DRUG-2026-000001")
    assert response.status_code == 401


def test_blockchain_disabled_returns_explicit_unavailable(monkeypatch):
    app.dependency_overrides[get_current_user] = user()
    monkeypatch.setattr(settings, "fabric_enabled", False)

    response = client.get("/api/blockchain/drugs/DRUG-2026-000001")

    assert response.status_code == 503
    assert response.json()["error"]["message"] == "Fabric integration is disabled"


def test_blockchain_gateway_url_and_timeout_are_configurable(monkeypatch):
    monkeypatch.setattr(settings, "fabric_enabled", True)
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={"success": True, "data": {"drugId": "DRUG-2026-000001"}},
        )
    )
    fabric_client = FabricClient(
        gateway_url="http://fabric-gateway.test",
        timeout=2.5,
        gateway_secret="secret",
        transport=transport,
    )

    assert fabric_client.gateway_url == "http://fabric-gateway.test"
    assert fabric_client.timeout == 2.5
    assert fabric_client.get_drug("DRUG-2026-000001")["drugId"] == "DRUG-2026-000001"


def test_fabric_client_preserves_missing_asset_error_code(monkeypatch):
    monkeypatch.setattr(settings, "fabric_enabled", True)
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            404,
            json={
                "success": False,
                "error": {"code": "ASSET_NOT_FOUND", "message": "Ledger asset not found"},
            },
        )
    )
    fabric_client = FabricClient(
        gateway_url="http://fabric-gateway.test", transport=transport
    )

    try:
        fabric_client.get_batch("BATCH-UNKNOWN")
    except FabricAssetNotFoundError as exc:
        assert str(exc) == "Ledger asset not found"
    else:
        raise AssertionError("missing ledger asset was not preserved")


def test_blockchain_success_forwards_public_id_without_uuid(monkeypatch):
    app.dependency_overrides[get_current_user] = user()
    monkeypatch.setattr(settings, "fabric_enabled", True)
    captured = {}

    def get_drug(self, drug_id):
        captured["drug_id"] = drug_id
        return {"drugId": drug_id, "transactionId": "real-fabric-id"}

    monkeypatch.setattr(blockchain_routes.FabricClient, "get_drug", get_drug)

    response = client.get("/api/blockchain/drugs/DRUG-2026-000001")

    assert response.status_code == 200
    assert captured["drug_id"] == "DRUG-2026-000001"
    assert "uuid" not in response.text.lower()


def test_blockchain_batch_write_forwards_explicit_identity_pair(monkeypatch):
    app.dependency_overrides[get_current_user] = user("MANUFACTURER")
    monkeypatch.setattr(settings, "fabric_enabled", True)
    captured = {}

    def create_batch(self, **payload):
        captured.update(payload)
        return {"batchId": payload["batch_id"], "transactionId": "tx-isolated"}

    monkeypatch.setattr(blockchain_routes.FabricClient, "create_batch", create_batch)
    response = client.post(
        "/api/blockchain/writes/batches",
        json={
            "batch_id": "BATCH-1", "drug_id": "DRUG-1", "manufacturer": "Example",
            "quantity": 3, "manufactured_date": "2026-01-01", "expiry_date": "2028-01-01",
            "qr_id": "QR-EXISTING-1", "rfid_id": "RFID-EXISTING-1",
        },
    )

    assert response.status_code == 200
    assert captured["qr_id"] == "QR-EXISTING-1"
    assert captured["rfid_id"] == "RFID-EXISTING-1"


def test_blockchain_batch_write_rejects_a_partial_identity_pair():
    app.dependency_overrides[get_current_user] = user("MANUFACTURER")
    response = client.post(
        "/api/blockchain/writes/batches",
        json={
            "batch_id": "BATCH-1", "drug_id": "DRUG-1", "manufacturer": "Example",
            "quantity": 3, "manufactured_date": "2026-01-01", "expiry_date": "2028-01-01",
            "qr_id": "QR-EXISTING-1",
        },
    )
    assert response.status_code == 422


def test_blockchain_gateway_failure_is_explicit(monkeypatch):
    app.dependency_overrides[get_current_user] = user()
    monkeypatch.setattr(settings, "fabric_enabled", True)

    def get_batch(self, batch_id):
        raise FabricGatewayError("Fabric gateway request failed")

    monkeypatch.setattr(blockchain_routes.FabricClient, "get_batch", get_batch)

    response = client.get("/api/blockchain/batches/BATCH-2026-000001")

    assert response.status_code == 502


def test_missing_ledger_asset_maps_to_http_404(monkeypatch):
    app.dependency_overrides[get_current_user] = user()
    monkeypatch.setattr(settings, "fabric_enabled", True)

    def missing(self, batch_id):
        raise FabricAssetNotFoundError("Ledger asset not found")

    monkeypatch.setattr(blockchain_routes.FabricClient, "get_batch", missing)
    response = client.get("/api/blockchain/batches/BATCH-UNKNOWN")

    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Ledger asset not found"


def test_blockchain_history_and_verify_identity(monkeypatch):
    app.dependency_overrides[get_current_user] = user()
    monkeypatch.setattr(settings, "fabric_enabled", True)
    captured = {}

    def get_history(self, batch_id):
        captured["history_batch_id"] = batch_id
        return [{"transactionId": "real-history-id"}]

    def verify(self, batch_id, qr_id, rfid_id):
        captured["verify"] = (batch_id, qr_id, rfid_id)
        return {"result": "AUTHENTIC"}

    monkeypatch.setattr(blockchain_routes.FabricClient, "get_batch_history", get_history)
    monkeypatch.setattr(blockchain_routes.FabricClient, "verify_identity", verify)

    history = client.get("/api/blockchain/batches/BATCH-2026-000001/history")
    verification = client.post(
        "/api/blockchain/verify-identity",
        json={
            "batch_id": "BATCH-2026-000001",
            "qr_id": "QR-MED-000001",
            "rfid_id": "RFID-MED-000001",
        },
    )

    assert history.status_code == 200
    assert verification.status_code == 200
    assert captured["history_batch_id"] == "BATCH-2026-000001"
    assert captured["verify"] == (
        "BATCH-2026-000001",
        "QR-MED-000001",
        "RFID-MED-000001",
    )


def test_fabric_client_unavailable_exception_is_explicit(monkeypatch):
    monkeypatch.setattr(settings, "fabric_enabled", False)
    fabric_client = FabricClient(gateway_url="http://unused")

    try:
        fabric_client.get_batch("BATCH-2026-000001")
    except FabricUnavailableError as exc:
        assert str(exc) == "Fabric integration is disabled"
    else:
        raise AssertionError("FabricUnavailableError was not raised")


def test_blockchain_write_requires_authentication():
    response = client.post(
        "/api/blockchain/writes/drugs",
        json={
            "drug_id": "DRUG-2026-000001",
            "name": "Example",
            "strength": "10mg",
            "manufacturer": "Example Labs",
        },
    )
    assert response.status_code == 401


def test_blockchain_write_disabled_does_not_fabricate_transaction(monkeypatch):
    app.dependency_overrides[get_current_user] = user("MANUFACTURER")
    monkeypatch.setattr(settings, "fabric_enabled", False)

    response = client.post(
        "/api/blockchain/writes/drugs",
        json={
            "drug_id": "DRUG-2026-000001",
            "name": "Example",
            "strength": "10mg",
            "manufacturer": "Example Labs",
        },
    )

    assert response.status_code == 503
    assert "transactionId" not in response.text


def test_blockchain_write_uses_authenticated_identity_and_real_transaction(monkeypatch):
    class NoBatchQuery:
        def filter(self, *args):
            return self

        def first(self):
            return None

    class NoBatchDB:
        def query(self, model):
            return NoBatchQuery()

    # The route persists the transaction id on the batch; keep the test
    # hermetic instead of requiring a live PostgreSQL server.
    app.dependency_overrides[get_db] = lambda: NoBatchDB()
    app.dependency_overrides[get_current_user] = (
        lambda: SimpleNamespace(
            role="REGULATOR", organization="Regulatory Authority", is_active=True
        )
    )
    monkeypatch.setattr(settings, "fabric_enabled", True)
    captured = {}

    def flag(self, batch_id, reason, risk_level, flagged_by):
        captured.update(
            batch_id=batch_id, reason=reason, risk_level=risk_level, flagged_by=flagged_by
        )
        return {"flagId": "FLAG_tx-1", "transactionId": "tx-1"}

    monkeypatch.setattr(blockchain_routes.FabricClient, "flag_drug", flag)
    response = client.post(
        "/api/blockchain/writes/flags",
        json={
            "batch_id": "BATCH-2026-000001",
            "reason": "temperature excursion",
            "risk_level": "HIGH",
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["transactionId"] == "tx-1"
    assert captured["flagged_by"] == "Regulatory Authority"
    assert captured["batch_id"] == "BATCH-2026-000001"


def test_blockchain_write_forbids_pharmacy_from_registering_drug():
    app.dependency_overrides[get_current_user] = user("PHARMACY")
    response = client.post(
        "/api/blockchain/writes/drugs",
        json={
            "drug_id": "DRUG-2026-000001",
            "name": "Example",
            "strength": "10mg",
            "manufacturer": "Example Labs",
        },
    )
    assert response.status_code == 403
