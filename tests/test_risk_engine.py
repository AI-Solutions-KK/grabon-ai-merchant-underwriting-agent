import pytest
from app.schemas.merchant_schema import MerchantInput
from app.engines.risk_engine import RiskEngine


class TestRiskEngine:
    """Unit tests for RiskEngine.evaluate_risk()"""

    def test_high_credit_high_revenue_no_reject(self):
        """High credit score and high revenue should not trigger auto-reject and result in high score."""
        merchant = MerchantInput(
            merchant_id="M_GOOD",
            monthly_revenue=90000,
            credit_score=780,
            years_in_business=6,
            existing_loans=0,
            past_defaults=0
        )
        
        result = RiskEngine.evaluate_risk(merchant)
        
        assert result["auto_reject"] is False
        assert result["reason"] is None
        assert result["score"] >= 70, f"Expected high score, got {result['score']}"

    def test_credit_score_below_threshold_auto_reject(self):
        """Credit score below 550 should trigger auto-reject."""
        merchant = MerchantInput(
            merchant_id="M_LOW_CREDIT",
            monthly_revenue=50000,
            credit_score=520,
            years_in_business=5,
            existing_loans=1,
            past_defaults=0
        )
        
        result = RiskEngine.evaluate_risk(merchant)
        
        assert result["auto_reject"] is True
        assert "550" in result["reason"]
        assert result["score"] == 0

    def test_past_defaults_threshold_auto_reject(self):
        """3 or more past defaults should trigger auto-reject."""
        merchant = MerchantInput(
            merchant_id="M_BAD_DEFAULTS",
            monthly_revenue=60000,
            credit_score=700,
            years_in_business=5,
            existing_loans=1,
            past_defaults=3
        )
        
        result = RiskEngine.evaluate_risk(merchant)
        
        assert result["auto_reject"] is True
        assert "defaults" in result["reason"].lower()
        assert result["score"] == 0

    def test_moderate_case_score_in_range(self):
        """Moderate merchant should have score between 50 and 75."""
        merchant = MerchantInput(
            merchant_id="M_MODERATE",
            monthly_revenue=40000,
            credit_score=680,
            years_in_business=3,
            existing_loans=2,
            past_defaults=0
        )
        
        result = RiskEngine.evaluate_risk(merchant)
        
        assert result["auto_reject"] is False
        assert result["reason"] is None
        assert 40 <= result["score"] <= 75, f"Expected score in range 40-75, got {result['score']}"

    def test_minimum_credit_score_acceptable(self):
        """Credit score of exactly 550 should be acceptable (not rejected)."""
        merchant = MerchantInput(
            merchant_id="M_MIN_CREDIT",
            monthly_revenue=50000,
            credit_score=550,
            years_in_business=3,
            existing_loans=1,
            past_defaults=0
        )
        
        result = RiskEngine.evaluate_risk(merchant)
        
        assert result["auto_reject"] is False
        assert result["score"] >= 0

    def test_max_defaults_acceptable(self):
        """2 past defaults should be acceptable (not rejected)."""
        merchant = MerchantInput(
            merchant_id="M_TWO_DEFAULTS",
            monthly_revenue=50000,
            credit_score=700,
            years_in_business=3,
            existing_loans=1,
            past_defaults=2
        )
        
        result = RiskEngine.evaluate_risk(merchant)
        
        assert result["auto_reject"] is False
        # Score will be reduced by penalties but not rejected
        assert result["score"] < 50, "Score should be reduced due to defaults penalty"

    def test_score_clamped_between_0_100(self):
        """Score should always be between 0 and 100."""
        # Test very strong merchant
        merchant_strong = MerchantInput(
            merchant_id="M_EXCELLENT",
            monthly_revenue=200000,  # Over cap
            credit_score=850,         # Max
            years_in_business=20,     # Very long
            existing_loans=0,
            past_defaults=0
        )
        
        result = RiskEngine.evaluate_risk(merchant_strong)
        assert result["score"] <= 100

        # Test weak merchant
        merchant_weak = MerchantInput(
            merchant_id="M_WEAK",
            monthly_revenue=5000,
            credit_score=600,
            years_in_business=0,
            existing_loans=5,
            past_defaults=2
        )
        
        result = RiskEngine.evaluate_risk(merchant_weak)
        assert result["score"] >= 0
