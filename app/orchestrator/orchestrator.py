from sqlalchemy.orm import Session
from app.engines.risk_engine import RiskEngine
from app.engines.decision_engine import DecisionEngine
from app.schemas.merchant_schema import MerchantInput
from app.schemas.decision_schema import UnderwritingDecision
from app.services.merchant_service import MerchantService
from app.services.application_service import RiskScoreService
from app.services.underwriting_agent import ClaudeUnderwritingAgent


class Orchestrator:
    """
    Central orchestrator for merchant underwriting process.
    
    Coordinates:
    - Deterministic risk scoring and decision making
    - AI-powered explanation generation via Claude
    - Data persistence and audit trail
    """
    
    @staticmethod
    def process_underwriting(merchant: MerchantInput, db: Session) -> UnderwritingDecision:
        """
        Process merchant underwriting request with AI-generated explanations.
        
        Flow:
        1. Save merchant via MerchantService
        2. Evaluate risk using RiskEngine.evaluate_risk()
        3. Evaluate decision using DecisionEngine.evaluate()
        4. Generate Claude AI explanation (with fallback)
        5. Construct UnderwritingDecision with AI-generated explanation
        6. Save risk result via RiskScoreService
        7. Return decision
        
        Args:
            merchant: MerchantInput containing merchant financial metrics
            db: SQLAlchemy database session
            
        Returns:
            UnderwritingDecision: Structured underwriting result with AI explanation
        """
        # Step 1: Save merchant to database
        MerchantService.create_merchant(db, merchant)
        
        # Step 2: Evaluate risk with hard rules and weighted scoring
        risk_result = RiskEngine.evaluate_risk(merchant)
        
        # Step 3: Evaluate decision based on risk result
        risk_tier, decision, _ = DecisionEngine.evaluate(risk_result)
        
        # Step 4: Generate Claude AI explanation (with automatic fallback)
        ai_explanation = ClaudeUnderwritingAgent.generate_explanation(
            merchant_data=merchant.dict(),
            risk_score=risk_result["score"],
            risk_tier=risk_tier,
            decision=decision
        )
        
        # Step 5: Construct UnderwritingDecision with AI explanation
        underwriting_decision = UnderwritingDecision(
            merchant_id=merchant.merchant_id,
            risk_score=risk_result["score"],
            risk_tier=risk_tier,
            decision=decision,
            explanation=ai_explanation
        )
        
        # Step 6: Save risk result to database
        RiskScoreService.create_risk_record(db, underwriting_decision)
        
        # Step 7: Return decision
        return underwriting_decision
