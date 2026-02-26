from sqlalchemy.orm import Session
from app.engines.risk_engine import RiskEngine
from app.engines.decision_engine import DecisionEngine
from app.schemas.merchant_schema import MerchantInput
from app.schemas.decision_schema import UnderwritingDecision
from app.services.merchant_service import MerchantService
from app.services.application_service import RiskScoreService


class Orchestrator:
    """
    Central orchestrator for merchant underwriting process.
    
    Coordinates deterministic risk scoring and decision making
    to produce structured underwriting decisions.
    """
    
    @staticmethod
    def process_underwriting(merchant: MerchantInput, db: Session) -> UnderwritingDecision:
        """
        Process merchant underwriting request with database persistence.
        
        Flow:
        1. Save merchant via MerchantService
        2. Evaluate risk using RiskEngine.evaluate_risk()
        3. Evaluate decision using DecisionEngine.evaluate()
        4. Construct UnderwritingDecision with results
        5. Save risk result via RiskScoreService
        6. Return decision
        
        Args:
            merchant: MerchantInput containing merchant financial metrics
            db: SQLAlchemy database session
            
        Returns:
            UnderwritingDecision: Structured underwriting result with decision
        """
        # Step 1: Save merchant to database
        MerchantService.create_merchant(db, merchant)
        
        # Step 2: Evaluate risk with hard rules and weighted scoring
        risk_result = RiskEngine.evaluate_risk(merchant)
        
        # Step 3: Evaluate decision based on risk result
        risk_tier, decision, explanation = DecisionEngine.evaluate(risk_result)
        
        # Step 4: Construct UnderwritingDecision with results
        underwriting_decision = UnderwritingDecision(
            merchant_id=merchant.merchant_id,
            risk_score=risk_result["score"],
            risk_tier=risk_tier,
            decision=decision,
            explanation=explanation
        )
        
        # Step 5: Save risk result to database
        RiskScoreService.create_risk_record(db, underwriting_decision)
        
        # Step 6: Return decision
        return underwriting_decision
