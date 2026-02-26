from app.schemas.merchant_schema import MerchantInput


class RiskEngine:
    """
    Deterministic risk scoring engine for merchant underwriting.
    
    Implements structured scoring with hard rejection rules and
    weighted component scoring.
    """
    
    # Hard rejection thresholds
    MIN_CREDIT_SCORE = 550
    MAX_PAST_DEFAULTS = 2
    
    @staticmethod
    def evaluate_risk(merchant: MerchantInput) -> dict:
        """
        Evaluate merchant risk with hard rules and weighted scoring.
        
        Hard rejection rules (override scoring):
        - Credit score < 550 → auto reject
        - Past defaults >= 3 → auto reject
        
        Scoring (if not rejected):
        - Credit score: normalized to 40 points (score / 850 * 40)
        - Monthly revenue: normalized to 25 points (cap at 100k)
        - Years in business: up to 15 points (3 pts per year, max 5 years)
        - Existing loans: penalty of 5 points each
        - Past defaults: penalty of 10 points each
        
        Args:
            merchant: MerchantInput containing merchant financial metrics
            
        Returns:
            dict: {
                "auto_reject": bool,
                "reason": str | None,
                "score": int
            }
        """
        # Step 1: Check hard rejection rules
        if merchant.credit_score < RiskEngine.MIN_CREDIT_SCORE:
            return {
                "auto_reject": True,
                "reason": f"Credit score {merchant.credit_score} is below minimum threshold of {RiskEngine.MIN_CREDIT_SCORE}",
                "score": 0
            }
        
        if merchant.past_defaults >= 3:
            return {
                "auto_reject": True,
                "reason": f"Too many past defaults ({merchant.past_defaults}). Maximum allowed is {RiskEngine.MAX_PAST_DEFAULTS}",
                "score": 0
            }
        
        # Step 2: Calculate weighted score
        score = 0.0
        
        # Credit score component (0-45 points)
        # Normalized to 850 max range
        credit_points = (merchant.credit_score / 850.0) * 45
        score += credit_points
        
        # Monthly revenue component (0-30 points)
        # Cap at 100k revenue
        revenue_normalized = min(merchant.monthly_revenue, 100000)
        revenue_points = (revenue_normalized / 100000) * 30
        score += revenue_points
        
        # Years in business component (0-15 points)
        # 3 points per year, max 5 years
        years_capped = min(merchant.years_in_business, 5)
        years_points = years_capped * 3
        score += years_points
        
        # Existing loans penalty (3 points each)
        loans_penalty = merchant.existing_loans * 3
        score -= loans_penalty
        
        # Past defaults penalty (10 points each)
        defaults_penalty = merchant.past_defaults * 10
        score -= defaults_penalty
        
        # Clamp between 0 and 100
        final_score = max(0, min(100, int(score)))
        
        return {
            "auto_reject": False,
            "reason": None,
            "score": final_score
        }
