from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.schemas.merchant_schema import MerchantInput
from app.schemas.decision_schema import UnderwritingDecision
from app.orchestrator.orchestrator import Orchestrator
from app.db.session import get_db

router = APIRouter(prefix="/api", tags=["underwriting"])


@router.post("/underwrite", response_model=UnderwritingDecision)
async def underwrite(merchant: MerchantInput, db: Session = Depends(get_db)) -> UnderwritingDecision:
    """
    Process merchant underwriting request.
    
    Takes merchant financial data and returns underwriting decision
    with risk score and approval status.
    
    Args:
        merchant: MerchantInput containing merchant financial metrics
        db: SQLAlchemy database session (injected via dependency)
        
    Returns:
        UnderwritingDecision: Underwriting result with risk assessment and decision
    """
    orchestrator = Orchestrator()
    decision = orchestrator.process_underwriting(merchant, db)
    return decision
