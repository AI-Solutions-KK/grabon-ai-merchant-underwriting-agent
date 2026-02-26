from sqlalchemy.orm import Session
from app.models.risk_score import RiskScore
from app.schemas.decision_schema import UnderwritingDecision


class RiskScoreService:
    """
    Service layer for risk score and underwriting decision persistence.
    
    Handles storage of risk assessment results in the database.
    """
    
    @staticmethod
    def create_risk_record(db: Session, decision: UnderwritingDecision) -> RiskScore:
        """
        Create and persist a risk score record.
        
        Args:
            db: SQLAlchemy database session
            decision: UnderwritingDecision schema with assessment results
            
        Returns:
            RiskScore: Created risk score record
        """
        db_risk = RiskScore(
            merchant_id=decision.merchant_id,
            risk_score=decision.risk_score,
            risk_tier=decision.risk_tier,
            decision=decision.decision,
            explanation=decision.explanation
        )
        db.add(db_risk)
        db.commit()
        db.refresh(db_risk)
        return db_risk
