import pytest
from app.engines.decision_engine import DecisionEngine


class TestDecisionEngine:
    """Unit tests for DecisionEngine.evaluate()"""

    def test_auto_reject_scenario(self):
        """Auto-reject scenario should return Tier 3 and REJECTED."""
        risk_result = {
            "auto_reject": True,
            "reason": "Credit score 520 is below minimum threshold of 550",
            "score": 0
        }
        
        tier, decision, explanation = DecisionEngine.evaluate(risk_result)
        
        assert tier == "Tier 3"
        assert decision == "REJECTED"
        assert "Auto-rejected" in explanation
        assert "Credit score" in explanation

    def test_score_high_tier1_approved(self):
        """Score >= 75 should return Tier 1 and APPROVED."""
        risk_result = {
            "auto_reject": False,
            "reason": None,
            "score": 80
        }
        
        tier, decision, explanation = DecisionEngine.evaluate(risk_result)
        
        assert tier == "Tier 1"
        assert decision == "APPROVED"
        assert "80" in explanation
        assert "Strong" in explanation or "strong" in explanation.lower()

    def test_score_medium_tier2_conditions(self):
        """Score 50-75 should return Tier 2 and APPROVED_WITH_CONDITIONS."""
        risk_result = {
            "auto_reject": False,
            "reason": None,
            "score": 60
        }
        
        tier, decision, explanation = DecisionEngine.evaluate(risk_result)
        
        assert tier == "Tier 2"
        assert decision == "APPROVED_WITH_CONDITIONS"
        assert "60" in explanation
        assert "Moderate" in explanation or "moderate" in explanation.lower()

    def test_score_low_tier3_rejected(self):
        """Score < 50 should return Tier 3 and REJECTED."""
        risk_result = {
            "auto_reject": False,
            "reason": None,
            "score": 40
        }
        
        tier, decision, explanation = DecisionEngine.evaluate(risk_result)
        
        assert tier == "Tier 3"
        assert decision == "REJECTED"
        assert "40" in explanation
        assert "threshold" in explanation.lower()

    def test_score_boundary_75(self):
        """Score of exactly 75 should be Tier 1."""
        risk_result = {
            "auto_reject": False,
            "reason": None,
            "score": 75
        }
        
        tier, decision, explanation = DecisionEngine.evaluate(risk_result)
        
        assert tier == "Tier 1"
        assert decision == "APPROVED"

    def test_score_boundary_50(self):
        """Score of exactly 50 should be Tier 2."""
        risk_result = {
            "auto_reject": False,
            "reason": None,
            "score": 50
        }
        
        tier, decision, explanation = DecisionEngine.evaluate(risk_result)
        
        assert tier == "Tier 2"
        assert decision == "APPROVED_WITH_CONDITIONS"

    def test_explanation_provided(self):
        """All decision paths should provide explanation."""
        test_cases = [
            {"auto_reject": True, "reason": "Too many defaults", "score": 0},
            {"auto_reject": False, "reason": None, "score": 80},
            {"auto_reject": False, "reason": None, "score": 60},
            {"auto_reject": False, "reason": None, "score": 40},
        ]
        
        for risk_result in test_cases:
            tier, decision, explanation = DecisionEngine.evaluate(risk_result)
            assert explanation is not None
            assert len(explanation) > 0, "Explanation should not be empty"
