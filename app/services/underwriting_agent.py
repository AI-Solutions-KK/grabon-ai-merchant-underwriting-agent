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
Be concise, data-driven, and reference specific financial AND behavioral metrics in your analysis.

When explaining decisions, consider:
1. Financial Metrics: Credit score, revenue, years in business, loan history, GMV
2. Behavioral Metrics: Customer loyalty (return rate), seasonality patterns, deal exclusivity,
   coupon engagement, customer concentration, order values, refund/return rates
3. Risk Indicators: Chargeback rates, refund rates suggest transaction risk
4. Market Position: Category, customer base size, and GMV trends indicate scale and stability"""
    
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
        decision: str,
        category_benchmark: dict = None,
        gmv_yoy_pct: float = None,
        score_breakdown: dict = None,
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
            return agent._call_claude(
                merchant_data, risk_score, risk_tier, decision,
                category_benchmark=category_benchmark or {},
                gmv_yoy_pct=gmv_yoy_pct,
                score_breakdown=score_breakdown or {},
            )
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
        decision: str,
        category_benchmark: dict = None,
        gmv_yoy_pct: float = None,
        score_breakdown: dict = None,
    ) -> str:
        """
        Call Claude API with underwriting context including behavioral metrics.
        
        Args:
            merchant_data: Merchant financial AND behavioral information
            risk_score: Risk score (0-100)
            risk_tier: Risk tier classification
            decision: Underwriting decision
            
        Returns:
            str: Claude-generated explanation
            
        Raises:
            Exception: If API call fails
        """
        # Extract financial metrics
        merchant_id = merchant_data.get('merchant_id', 'N/A')
        monthly_revenue = merchant_data.get('monthly_revenue', 0)
        credit_score = merchant_data.get('credit_score', 0)
        years_in_business = merchant_data.get('years_in_business', 0)
        existing_loans = merchant_data.get('existing_loans', 0)
        past_defaults = merchant_data.get('past_defaults', 0)
        gmv = merchant_data.get('gmv', 0)
        refund_rate = merchant_data.get('refund_rate', 0)
        chargeback_rate = merchant_data.get('chargeback_rate', 0)

        # Extract behavioral metrics
        category = merchant_data.get('category', 'General')
        coupon_redemption_rate = merchant_data.get('coupon_redemption_rate', 0)
        unique_customer_count = merchant_data.get('unique_customer_count', 0)
        customer_return_rate = merchant_data.get('customer_return_rate', 0)
        avg_order_value = merchant_data.get('avg_order_value', 0)
        seasonality_index = merchant_data.get('seasonality_index', 1.0)
        deal_exclusivity_rate = merchant_data.get('deal_exclusivity_rate', 0)
        return_and_refund_rate = merchant_data.get('return_and_refund_rate', 0)

        # GMV trend
        monthly_gmv_12m = merchant_data.get('monthly_gmv_12m') or []
        if gmv_yoy_pct is not None:
            direction = "growing" if gmv_yoy_pct > 0 else "declining"
            gmv_trend = f"{direction} ({gmv_yoy_pct:+.1f}% H1→H2)"
        elif len(monthly_gmv_12m) >= 4:
            recent = sum(monthly_gmv_12m[-3:]) / 3
            prior = sum(monthly_gmv_12m[-6:-3]) / 3
            if prior > 0:
                pct = ((recent - prior) / prior) * 100
                gmv_trend = f"{'Growing' if pct > 0 else 'Declining'} ({pct:+.1f}%)"
            else:
                gmv_trend = "Stable"
        else:
            gmv_trend = "Insufficient data"

        # Category benchmarks
        bench = category_benchmark or {}
        bench_refund = bench.get('refund_rate', 0.045)
        bench_chargeback = bench.get('chargeback_rate', 0.015)
        bench_crr = bench.get('customer_return_rate', 0.35)
        vs_refund = "below" if refund_rate < bench_refund else "above"
        vs_chargeback = "below" if chargeback_rate < bench_chargeback else "above"
        vs_crr = "above" if customer_return_rate > bench_crr else "below"

        context = f"""
FINANCIAL PROFILE:
- Merchant ID: {merchant_id} (Category: {category})
- Monthly Revenue: ₹{monthly_revenue:,.0f}
- Annual GMV: ₹{gmv * 12:,.0f}  (monthly snapshot: ₹{gmv:,.0f})
- Credit Score: {credit_score}
- Years in Business: {years_in_business}
- Active Loans: {existing_loans}
- Past Defaults: {past_defaults}

TRANSACTION METRICS:
- Refund Rate: {refund_rate*100:.1f}%  ({vs_refund} category avg of {bench_refund*100:.1f}%)
- Chargeback Rate: {chargeback_rate*100:.1f}%  ({vs_chargeback} category avg of {bench_chargeback*100:.1f}%)
- Return & Refund Rate: {return_and_refund_rate*100:.1f}%

CUSTOMER BEHAVIOR:
- Unique Customers: {unique_customer_count:,}
- Customer Return Rate: {customer_return_rate*100:.0f}%  ({vs_crr} category avg of {bench_crr*100:.0f}%)
- Coupon Engagement: {coupon_redemption_rate*100:.0f}%
- Deal Exclusivity: {deal_exclusivity_rate*100:.0f}%
- Average Order Value: ₹{avg_order_value:,.0f}
- Seasonality Index: {seasonality_index:.2f}x (peak-to-trough ratio)
- GMV Trend: {gmv_trend}

UNDERWRITING ASSESSMENT:
- Computed Risk Score: {risk_score}/100
- Risk Tier: {risk_tier}
- Decision: {decision}

TASK: Generate 3–5 professional sentences explaining this underwriting decision.
REQUIREMENTS:
1. Cite specific numbers (e.g., "credit score of {credit_score}", "refund rate of {refund_rate*100:.1f}%")
2. Compare at least one metric to its category average benchmark
3. Reference the GMV trend and at least one behavioral indicator (customer return rate, seasonality)
4. Explain WHY the decision is {decision} in formal underwriting language
5. For REJECTED: explain which specific factors caused rejection
6. Return ONLY the explanation — no headers, no bullet points, no JSON"""

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
        Incorporates both financial and behavioral metrics.
        
        Args:
            merchant_data: Merchant financial and behavioral information
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
        
        # Behavioral metrics
        customer_return_rate = merchant_data.get('customer_return_rate', 0)
        chargeback_rate = merchant_data.get('chargeback_rate', 0)
        refund_rate = merchant_data.get('refund_rate', 0)
        unique_customers = merchant_data.get('unique_customer_count', 0)
        
        # Build behavioral insight
        behavioral_insight = ""
        if unique_customers > 0:
            behavioral_insight += f"With {unique_customers:,} unique customers and {customer_return_rate*100:.0f}% returning, "
        if chargeback_rate > 0 or refund_rate > 0:
            behavioral_insight += f"transaction quality shows {chargeback_rate*100:.1f}% chargeback and {refund_rate*100:.1f}% refund rates. "
        if not behavioral_insight:
            behavioral_insight = "Behavioral metrics align with the risk profile. "
        
        fallback = (
            f"Merchant {merchant_id} has been assessed with a risk score of {risk_score}/100, "
            f"classified as {risk_tier}. The decision to {decision.lower().replace('_', ' ')} is supported by: "
            f"credit score of {credit_score}, monthly revenue of ${revenue:,.0f}, {years} years in operations, "
            f"and {defaults} historical defaults. {behavioral_insight}"
            f"This profile aligns with {risk_tier} underwriting standards."
        )
        
        return fallback
