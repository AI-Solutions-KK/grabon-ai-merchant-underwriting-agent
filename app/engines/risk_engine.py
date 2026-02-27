from app.schemas.merchant_schema import MerchantInput


class RiskEngine:
    """
    Deterministic risk scoring engine for merchant underwriting.
    
    Scoring breakdown (max 100):
      Credit score         : 0–40 pts
      Monthly revenue      : 0–25 pts  (capped at ₹1,00,000)
      Years in business    : 0–12 pts  (2.4 pts/yr, max 5 yrs)
      Customer return rate : 0–8  pts  (loyalty signal)
      Deal exclusivity     : 0–5  pts  (competitive moat)
      GMV growth (YoY)     : 0–10 pts  (growth bonus)

    Penalties:
      Existing loans       : −3 pts each
      Past defaults        : −10 pts each
      Refund rate > 15%    : −10 pts; > 30% → −20 pts
      Chargeback > 5%      : −8 pts;  > 10% → −15 pts
      Return & refund > 10%: −8 pts
      High seasonality (>2): −5 pts  (unpredictable revenue)

    Hard-reject rules (override score):
      Credit score < 550  → auto reject
      Past defaults ≥ 3   → auto reject
    """

    MIN_CREDIT_SCORE = 550
    MAX_PAST_DEFAULTS = 2

    # Category average benchmarks — used in explanations
    CATEGORY_BENCHMARKS = {
        "Electronics":        {"refund_rate": 0.035, "chargeback_rate": 0.012, "customer_return_rate": 0.38},
        "Fashion":            {"refund_rate": 0.060, "chargeback_rate": 0.015, "customer_return_rate": 0.32},
        "Food & Beverage":    {"refund_rate": 0.018, "chargeback_rate": 0.008, "customer_return_rate": 0.55},
        "Health & Beauty":    {"refund_rate": 0.055, "chargeback_rate": 0.020, "customer_return_rate": 0.28},
        "Home & Living":      {"refund_rate": 0.040, "chargeback_rate": 0.010, "customer_return_rate": 0.40},
        "Sports & Outdoors":  {"refund_rate": 0.070, "chargeback_rate": 0.025, "customer_return_rate": 0.25},
        "Toys & Games":       {"refund_rate": 0.045, "chargeback_rate": 0.018, "customer_return_rate": 0.30},
        "Automotive":         {"refund_rate": 0.020, "chargeback_rate": 0.008, "customer_return_rate": 0.55},
        "Books & Stationery": {"refund_rate": 0.025, "chargeback_rate": 0.005, "customer_return_rate": 0.42},
        "Jewellery":          {"refund_rate": 0.022, "chargeback_rate": 0.006, "customer_return_rate": 0.60},
    }

    @staticmethod
    def get_category_benchmark(category: str) -> dict:
        return RiskEngine.CATEGORY_BENCHMARKS.get(
            category,
            {"refund_rate": 0.045, "chargeback_rate": 0.015, "customer_return_rate": 0.35}
        )

    @staticmethod
    def evaluate_risk(merchant: MerchantInput) -> dict:
        """
        Evaluate merchant risk. Returns:
            {
              "auto_reject": bool,
              "reason": str | None,
              "score": int,           # 0–100
              "score_breakdown": dict,
              "category_benchmark": dict,
              "gmv_yoy_pct": float | None,
            }
        """
        # ── Hard rejection rules ────────────────────────────────
        if merchant.credit_score < RiskEngine.MIN_CREDIT_SCORE:
            return {
                "auto_reject": True,
                "reason": (
                    f"Credit score of {merchant.credit_score} is below the minimum "
                    f"threshold of {RiskEngine.MIN_CREDIT_SCORE}."
                ),
                "score": 0, "score_breakdown": {}, "category_benchmark": {},
                "gmv_yoy_pct": None,
            }

        if merchant.past_defaults >= 3:
            return {
                "auto_reject": True,
                "reason": (
                    f"Past default count of {merchant.past_defaults} exceeds the "
                    f"maximum allowed threshold of {RiskEngine.MAX_PAST_DEFAULTS}."
                ),
                "score": 0, "score_breakdown": {}, "category_benchmark": {},
                "gmv_yoy_pct": None,
            }

        breakdown = {}
        score = 0.0

        # ── Positive components ─────────────────────────────────

        # Credit score (0–40)
        cs_pts = (merchant.credit_score / 850.0) * 40
        score += cs_pts
        breakdown["credit_score"] = round(cs_pts, 1)

        # Monthly revenue (0–25, capped at ₹1,00,000)
        rev_pts = (min(merchant.monthly_revenue, 100_000) / 100_000) * 25
        score += rev_pts
        breakdown["revenue"] = round(rev_pts, 1)

        # Years in business (0–12, 2.4 pts/yr, max 5 yrs)
        yr_pts = min(merchant.years_in_business, 5) * 2.4
        score += yr_pts
        breakdown["years_in_business"] = round(yr_pts, 1)

        # Customer return rate loyalty bonus (0–8)
        crr = merchant.customer_return_rate or 0.0
        crr_pts = crr * 8.0          # 100% return rate → 8 pts
        score += crr_pts
        breakdown["customer_return_rate"] = round(crr_pts, 1)

        # Deal exclusivity bonus (0–5)
        der = merchant.deal_exclusivity_rate or 0.0
        excl_pts = der * 5.0
        score += excl_pts
        breakdown["deal_exclusivity"] = round(excl_pts, 1)

        # GMV YoY growth bonus (0–10) — computed from monthly_gmv_12m
        gmv_yoy_pct = None
        gmv_list = merchant.monthly_gmv_12m or []
        if len(gmv_list) >= 12:
            h1_avg = sum(gmv_list[:6]) / 6
            h2_avg = sum(gmv_list[6:]) / 6
            if h1_avg > 0:
                gmv_yoy_pct = ((h2_avg - h1_avg) / h1_avg) * 100
                growth_pts = max(0, min(10, gmv_yoy_pct * 0.5))  # 20% growth → 10 pts
                score += growth_pts
                breakdown["gmv_growth"] = round(growth_pts, 1)
        if "gmv_growth" not in breakdown:
            breakdown["gmv_growth"] = 0.0

        # ── Penalties ───────────────────────────────────────────

        # Existing loans
        loan_pen = merchant.existing_loans * 3
        score -= loan_pen
        breakdown["loans_penalty"] = -round(loan_pen, 1)

        # Past defaults
        def_pen = merchant.past_defaults * 10
        score -= def_pen
        breakdown["defaults_penalty"] = -round(def_pen, 1)

        # Refund rate
        rr = merchant.refund_rate or 0.0
        if rr > 0.30:
            score -= 20; breakdown["refund_penalty"] = -20
        elif rr > 0.15:
            score -= 10; breakdown["refund_penalty"] = -10
        else:
            breakdown["refund_penalty"] = 0

        # Chargeback rate
        cb = merchant.chargeback_rate or 0.0
        if cb > 0.10:
            score -= 15; breakdown["chargeback_penalty"] = -15
        elif cb > 0.05:
            score -= 8; breakdown["chargeback_penalty"] = -8
        else:
            breakdown["chargeback_penalty"] = 0

        # Return & refund rate
        rfr = merchant.return_and_refund_rate or 0.0
        if rfr > 0.10:
            score -= 8; breakdown["return_refund_penalty"] = -8
        else:
            breakdown["return_refund_penalty"] = 0

        # High seasonality volatility penalty
        si = merchant.seasonality_index or 1.0
        if si > 2.0:
            score -= 5; breakdown["seasonality_penalty"] = -5
        else:
            breakdown["seasonality_penalty"] = 0

        final_score = max(0, min(100, int(score)))
        benchmark = RiskEngine.get_category_benchmark(merchant.category or "")

        return {
            "auto_reject": False,
            "reason": None,
            "score": final_score,
            "score_breakdown": breakdown,
            "category_benchmark": benchmark,
            "gmv_yoy_pct": round(gmv_yoy_pct, 1) if gmv_yoy_pct is not None else None,
        }
