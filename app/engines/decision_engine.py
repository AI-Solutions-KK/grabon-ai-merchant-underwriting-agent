class DecisionEngine:
    """
    Decision engine for merchant underwriting evaluation.
    
    Implements hybrid rule-based and score-based evaluation logic.
    """

    @staticmethod
    def evaluate(risk_result: dict) -> tuple[str, str, str]:
        """
        Evaluate risk result and produce decision tier, approval status, and explanation.

        Decision logic:
        - If auto_reject is True: Tier 3, REJECTED with explicit reason
        - Else, use score thresholds:
            - score >= 75: Tier 1 (APPROVED)
            - 50 <= score < 75: Tier 2 (APPROVED_WITH_CONDITIONS)
            - score < 50: Tier 3 (REJECTED)

        Args:
            risk_result: dict from RiskEngine.evaluate_risk() containing:
                - auto_reject: bool
                - reason: str | None
                - score: int

        Returns:
            tuple[str, str, str]: (risk_tier, decision, explanation)
        """
        # Handle hard rejection rules
        if risk_result["auto_reject"]:
            return (
                "Tier 3",
                "REJECTED",
                f"Auto-rejected: {risk_result['reason']}"
            )
        
        # Score-based evaluation
        score = risk_result["score"]
        
        if score >= 75:
            return (
                "Tier 1",
                "APPROVED",
                f"Strong credit profile and financial metrics. Risk score: {score}/100. Approved for full credit line."
            )
        elif 50 <= score < 75:
            return (
                "Tier 2",
                "APPROVED_WITH_CONDITIONS",
                f"Moderate risk profile. Risk score: {score}/100. Approved with conditions or lower credit limit."
            )
        else:
            return (
                "Tier 3",
                "REJECTED",
                f"Risk score {score}/100 below approval threshold. Consider reapplying after improving financial metrics."
            )
