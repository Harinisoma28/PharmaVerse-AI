import logging

from fastapi import FastAPI
from fastapi import Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from app.api.routes.batch import router as batch_router
from app.api.routes.audit import router as audit_router
from app.api.routes.drug import router as drug_router
from app.api.routes.qr import router as qr_router
from app.api.routes.rfid import router as rfid_router
from app.api.routes.shipment import router as shipment_router
from app.api.routes.verification import router as verification_router
from app.core.config import settings
from app.core.responses import (
    INTERNAL_SERVER_ERROR,
    VALIDATION_ERROR,
    error_code_for_status,
    error_response,
)
from app.api.routes.auth import router as auth_router
from app.api.routes.ai import router as ai_router
from app.api.routes.simulation import router as simulation_router
from app.api.routes.blockchain import router as blockchain_router
from app.api.routes.ml import router as ml_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.admin import router as admin_router

def _serializable_errors(errors: list[dict]) -> list[dict]:
    """Make Pydantic error details JSON-safe.

    Errors raised by custom validators carry the original exception object in
    ``ctx["error"]``; that is not JSON serializable and previously turned
    every such validation failure into an HTTP 500.
    """
    cleaned = []
    for error in errors:
        error = dict(error)
        ctx = error.get("ctx")
        if isinstance(ctx, dict):
            error["ctx"] = {
                key: (str(value) if isinstance(value, Exception) else value)
                for key, value in ctx.items()
            }
        # Never echo submitted credentials back in an error response.
        if error.get("loc") and error["loc"][-1] == "password":
            error["input"] = "***"
        elif isinstance(error.get("input"), dict) and "password" in error["input"]:
            error["input"] = {**error["input"], "password": "***"}
        cleaned.append(error)
    return jsonable_encoder(cleaned)


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
)


# Registered for Starlette's HTTPException (the base class of FastAPI's) so
# that framework-raised errors such as unknown routes (404) or wrong methods
# (405) also use the standard error envelope.
@app.exception_handler(HTTPException)
async def http_exception_handler(
    request: Request,
    exc: HTTPException,
):
    detail = exc.detail
    message = detail if isinstance(detail, str) else "Request failed"
    details = detail if isinstance(detail, (dict, list)) else None

    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(
            error_code_for_status(exc.status_code),
            message,
            details,
        ),
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
):
    return JSONResponse(
        status_code=422,
        content=error_response(
            VALIDATION_ERROR,
            "Request validation failed",
            _serializable_errors(exc.errors()),
        ),
    )


@app.exception_handler(Exception)
async def unexpected_exception_handler(
    request: Request,
    exc: Exception,
):
    logging.getLogger(__name__).exception(
        "Unhandled application exception",
        exc_info=exc,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response(
            INTERNAL_SERVER_ERROR,
            "An unexpected server error occurred",
        ),
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=list({
        *settings.cors_origins.split(","),
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    }),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(drug_router)
app.include_router(batch_router)
app.include_router(shipment_router)
app.include_router(qr_router)
app.include_router(rfid_router)
app.include_router(verification_router)
app.include_router(audit_router)
app.include_router(ai_router)
app.include_router(simulation_router)
app.include_router(blockchain_router)
app.include_router(ml_router)
app.include_router(dashboard_router)
app.include_router(admin_router)
@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": "0.1.0",
    }
