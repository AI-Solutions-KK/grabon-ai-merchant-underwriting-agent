from app.engines.risk_engine import RiskEngine
from app.engines.decision_engine import DecisionEngine
from app.schemas.merchant_schema import MerchantInput
from app.schemas.decision_schema import UnderwritingDecision


class Orchestrator:
    """
    Central orchestrator for merchant underwriting process.
    
    Coordinates deterministic risk scoring and decision making
    to produce structured underwriting decisions.
    """
    
    @staticmethod
    def process_underwriting(merchant: MerchantInput) -> UnderwritingDecision:
        """
        Process merchant underwriting request.
        
        Flow:
        1. Calculate risk score using RiskEngine
        2. Evaluate score using DecisionEngine
        3. Construct UnderwritingDecision with results
        
        Args:
            merchant: MerchantInput containing merchant financial metrics
            
        Returns:
            UnderwritingDecision: Structured underwriting result with decision
        """
        # Step 1: Calculate risk score
        risk_score = RiskEngine.calculate_score(merchant)
        
        # Step 2: Evaluate score and get tier and decision
        risk_tier, decision = DecisionEngine.evaluate(risk_score)
        
        # Step 3: Construct and return UnderwritingDecision
        underwriting_decision = UnderwritingDecision(
            merchant_id=merchant.merchant_id,
            risk_score=risk_score,
            risk_tier=risk_tier,
            decision=decision,
            explanation=f"Risk score: {risk_score}. Classification: {risk_tier}. "
                        f"Based on credit score ({merchant.credit_score}), "
                        f"business history ({merchant.years_in_business} years), "
                        f"and financial obligations ({merchant.existing_loans} loans, "
                        f"{merchant.past_defaults} defaults)."
        )
        
        return underwriting_decision
