from app.schemas.merchant_schema import MerchantInput


class RiskEngine:
    """
    Deterministic risk scoring engine for merchant underwriting.
    
    Produces a risk score (0-100) based on merchant financial metrics
    and business history.
    """
    
    @staticmethod
    def calculate_score(merchant: MerchantInput) -> int:
        """
        Calculate deterministic risk score for a merchant.
        
        Scoring logic:
        - Base score: 100
        - Deduct for poor credit: (100 - credit_score) * 0.4
        - Deduct for past defaults: past_defaults * 10
        - Deduct for existing loans: existing_loans * 5
        - Add for business longevity: years_in_business * 2
        - Clamp result between 0-100
        
        Args:
            merchant: MerchantInput containing merchant financial metrics
            
        Returns:
            int: Risk score between 0 (lowest risk) and 100 (highest risk)
        """
        # Start with base score
        score = 100.0
        
        # Deduct for poor credit score
        credit_deduction = (100 - merchant.credit_score) * 0.4
        score -= credit_deduction
        
        # Deduct for past defaults
        defaults_deduction = merchant.past_defaults * 10
        score -= defaults_deduction
        
        # Deduct for existing loans
        loans_deduction = merchant.existing_loans * 5
        score -= loans_deduction
        
        # Add for years in business
        longevity_bonus = merchant.years_in_business * 2
        score += longevity_bonus
        
        # Clamp between 0 and 100
        risk_score = max(0, min(100, int(score)))
        
        return risk_score
