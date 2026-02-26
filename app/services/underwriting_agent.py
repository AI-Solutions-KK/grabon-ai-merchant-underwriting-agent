import os
from anthropic import Anthropic


class ClaudeUnderwritingAgent:
    """
    AI-powered underwriting analyst using Claude.
    
    Generates professional, explainable reasoning for merchant underwriting decisions.
    """
    
    # Claude model configuration
    MODEL = "claude-3-haiku-20240307"
    MAX_TOKENS = 300
    TEMPERATURE = 0.3
    
    # System prompt for Claude
    SYSTEM_PROMPT = """You are a financial underwriting analyst for GrabCredit and GrabInsurance.
Your role is to provide professional, formal explanations for underwriting decisions.
Be concise, data-driven, and reference specific financial metrics in your analysis."""
    
    def __init__(self):
        """Initialize Claude API client."""
        self.client = Anthropic()
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
    
    @staticmethod
    def generate_explanation(
        merchant_data: dict,
        risk_score: int,
        risk_tier: str,
        decision: str
    ) -> str:
        """
        Generate Claude-powered explanation for underwriting decision.
        
        Args:
            merchant_data: Dict with merchant financial metrics
            risk_score: Computed risk score (0-100)
            risk_tier: Risk tier classification (Tier 1, 2, or 3)
            decision: Final decision (APPROVED, APPROVED_WITH_CONDITIONS, REJECTED)
            
        Returns:
            str: 3-5 sentence professional explanation
        """
        try:
            agent = ClaudeUnderwritingAgent()
            return agent._call_claude(merchant_data, risk_score, risk_tier, decision)
        except Exception as e:
            # Return fallback explanation if Claude fails
            return ClaudeUnderwritingAgent._fallback_explanation(
                merchant_data, risk_score, risk_tier, decision, str(e)
            )
    
    def _call_claude(
        self,
        merchant_data: dict,
        risk_score: int,
        risk_tier: str,
        decision: str
    ) -> str:
        """
        Call Claude API with underwriting context.
        
        Args:
            merchant_data: Merchant financial information
            risk_score: Risk score (0-100)
            risk_tier: Risk tier classification
            decision: Underwriting decision
            
        Returns:
            str: Claude-generated explanation
            
        Raises:
            Exception: If API call fails
        """
        # Build merchant context for Claude
        context = f"""
Merchant Underwriting Data:
- Merchant ID: {merchant_data.get('merchant_id', 'N/A')}
- Monthly Revenue: ${merchant_data.get('monthly_revenue', 0):,.2f}
- Credit Score: {merchant_data.get('credit_score', 0)}
- Years in Business: {merchant_data.get('years_in_business', 0)}
- Existing Loans: {merchant_data.get('existing_loans', 0)}
- Past Defaults: {merchant_data.get('past_defaults', 0)}

Underwriting Assessment:
- Computed Risk Score: {risk_score}/100
- Risk Tier: {risk_tier}
- Decision: {decision}

Task: Generate 3–5 professional sentences explaining why this underwriting decision was made.
Must reference at least 3 specific data points from the merchant profile.
Use formal, underwriting-appropriate language.
Return only the explanation text, no additional commentary."""

        # Call Claude API
        message = self.client.messages.create(
            model=self.MODEL,
            max_tokens=self.MAX_TOKENS,
            temperature=self.TEMPERATURE,
            system=self.SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": context
                }
            ]
        )
        
        # Extract explanation from response
        explanation = message.content[0].text.strip()
        return explanation
    
    @staticmethod
    def _fallback_explanation(
        merchant_data: dict,
        risk_score: int,
        risk_tier: str,
        decision: str,
        error_msg: str = None
    ) -> str:
        """
        Fallback explanation if Claude fails.
        
        Args:
            merchant_data: Merchant financial information
            risk_score: Risk score (0-100)
            risk_tier: Risk tier classification
            decision: Underwriting decision
            error_msg: Optional error message for logging
            
        Returns:
            str: Deterministic fallback explanation
        """
        merchant_id = merchant_data.get('merchant_id', 'Unknown')
        credit_score = merchant_data.get('credit_score', 0)
        revenue = merchant_data.get('monthly_revenue', 0)
        defaults = merchant_data.get('past_defaults', 0)
        years = merchant_data.get('years_in_business', 0)
        
        fallback = (
            f"Merchant {merchant_id} has been classified as {risk_tier} with a computed risk score of {risk_score}/100. "
            f"The decision to {decision.lower().replace('_', ' ')} is based on key financial metrics: "
            f"credit score of {credit_score}, monthly revenue of ${revenue:,.0f}, "
            f"{years} years in business, and {defaults} past defaults. "
            f"This merchant profile aligns with {risk_tier} underwriting criteria."
        )
        
        return fallback
