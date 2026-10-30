from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.schemas.fda import FDALiveSummaryResponse
from app.core.security import get_current_user
from app.database.connection import get_db
from app.models.user import User
from app.schemas.ai import AIAnalysisRequest, AIAnalysisResponse
from app.services.ai_adapter import AIAdapter
from app.services.fda_reference import FDAReferenceService


router = APIRouter(
    prefix="/api/ai",
    tags=["AI"],
)

fda_service = FDAReferenceService()


@router.post(
    "/analyze",
    response_model=AIAnalysisResponse,
)
def analyze_shipment(
    request: AIAnalysisRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return AIAdapter().analyze(request, db)


@router.get("/fda-reference")
def fda_reference(
    drug_name: str,
    limit: int = 10,
    current_user: User = Depends(get_current_user),
):
    return fda_service.search(drug_name, limit)
@router.get(
    "/fda-live/summary",
    response_model=FDALiveSummaryResponse,
)
def fda_live_summary(
    current_user: User = Depends(get_current_user),
):
    return fda_service.live_summary()