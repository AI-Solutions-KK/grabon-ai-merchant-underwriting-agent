from enum import Enum
from pydantic import BaseModel, Field


class RiskTier(str, Enum):
    """Risk tier classification for underwriting decisions."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


class UnderwritingDecision(str, Enum):
    """Final underwriting decision outcomes."""
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PENDING_REVIEW = "PENDING_REVIEW"


class UnderwritingDecision(BaseModel):
    """
    Pydantic model for underwriting result and final decision.
    
    Encapsulates the risk assessment outcome and decision rationale.
    """
    merchant_id: str = Field(..., description="Unique identifier for the merchant")
    risk_score: int = Field(..., ge=0, le=100, description="Risk score on a scale of 0-100")
    risk_tier: str = Field(..., description="Risk tier classification (LOW, MEDIUM, HIGH, VERY_HIGH)")
    decision: str = Field(..., description="Final underwriting decision (APPROVED, REJECTED, PENDING_REVIEW)")
    explanation: str = Field(..., description="Detailed explanation for the decision")

    class Config:
        json_schema_extra = {
            "example": {
                "merchant_id": "MERCH_12345",
                "risk_score": 35,
                "risk_tier": "LOW",
                "decision": "APPROVED",
                "explanation": "Strong credit score and stable revenue history. Risk score below threshold."
            }
        }
