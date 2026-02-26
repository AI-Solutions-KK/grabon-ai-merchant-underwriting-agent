class DecisionEngine:
    """Decision engine for merchant underwriting evaluation."""

    @staticmethod
    def evaluate(score: int) -> tuple[str, str]:
        """
        Evaluate risk score and produce decision tier and approval status.

        Score ranges:
        - score >= 75: Tier 1 (APPROVED)
        - 50 <= score < 75: Tier 2 (APPROVED_WITH_CONDITIONS)
        - score < 50: Tier 3 (REJECTED)

        Args:
            score: Risk score between 0-100

        Returns:
            tuple[str, str]: (risk_tier, decision)
        """
        if score >= 75:
            return ("Tier 1", "APPROVED")
        elif 50 <= score < 75:
            return ("Tier 2", "APPROVED_WITH_CONDITIONS")
        else:
            return ("Tier 3", "REJECTED")
