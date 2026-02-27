from app.db.base import Base
from app.db.session import engine, SessionLocal

# Import all models to register them with Base
from app.models.merchant import Merchant
from app.models.risk_score import RiskScore
from app.models.system_config import SystemConfig

# Fixed 10-merchant dataset for evaluator demo
# Tier distribution: Tier 1 × 6, Tier 2 × 2, Tier 3 REJECTED × 2 (M004, M006)
SAMPLE_MERCHANTS = [
    {
        "merchant_id": "GRAB_M001", "category": "Electronics",
        "monthly_revenue": 850000,  "credit_score": 760, "years_in_business": 7,
        "existing_loans": 1, "past_defaults": 0,
        "chargeback_rate": 0.008, "refund_rate": 0.02,
        "avg_order_value": 4500,  "unique_customer_count": 3200,
        "customer_return_rate": 0.45, "coupon_redemption_rate": 0.12,
        "seasonality_index": 1.3, "deal_exclusivity_rate": 0.30,
        "return_and_refund_rate": 0.02,
        # Growing trend — YoY ≈ +20%
        "monthly_gmv_12m": [800000, 820000, 840000, 810000, 850000, 870000,
                             890000, 880000, 900000, 920000, 940000, 960000],
    },
    {
        "merchant_id": "GRAB_M002", "category": "Fashion",
        "monthly_revenue": 620000,  "credit_score": 720, "years_in_business": 5,
        "existing_loans": 0, "past_defaults": 0,
        "chargeback_rate": 0.010, "refund_rate": 0.04,
        "avg_order_value": 2200,  "unique_customer_count": 5100,
        "customer_return_rate": 0.38, "coupon_redemption_rate": 0.25,
        "seasonality_index": 1.6, "deal_exclusivity_rate": 0.20,
        "return_and_refund_rate": 0.04,
        # Stable with seasonal peaks (festive quarters)
        "monthly_gmv_12m": [580000, 590000, 600000, 650000, 680000, 620000,
                             600000, 590000, 610000, 630000, 620000, 640000],
    },
    {
        "merchant_id": "GRAB_M003", "category": "Food & Beverage",
        "monthly_revenue": 450000,  "credit_score": 690, "years_in_business": 4,
        "existing_loans": 1, "past_defaults": 0,
        "chargeback_rate": 0.005, "refund_rate": 0.01,
        "avg_order_value": 800,   "unique_customer_count": 8900,
        "customer_return_rate": 0.62, "coupon_redemption_rate": 0.40,
        "seasonality_index": 1.1, "deal_exclusivity_rate": 0.50,
        "return_and_refund_rate": 0.01,
        # Steady growth — strong repeat customer base
        "monthly_gmv_12m": [400000, 420000, 430000, 440000, 450000, 460000,
                             455000, 465000, 470000, 475000, 480000, 490000],
    },
    {
        # TIER 3 REJECTED — high defaults, many loans, declining GMV
        "merchant_id": "GRAB_M004", "category": "Health & Beauty",
        "monthly_revenue": 380000,  "credit_score": 640, "years_in_business": 2,
        "existing_loans": 3, "past_defaults": 2,
        "chargeback_rate": 0.022, "refund_rate": 0.06,
        "avg_order_value": 1800,  "unique_customer_count": 1200,
        "customer_return_rate": 0.22, "coupon_redemption_rate": 0.08,
        "seasonality_index": 1.2, "deal_exclusivity_rate": 0.10,
        "return_and_refund_rate": 0.06,
        # Declining trend — losing customers
        "monthly_gmv_12m": [450000, 420000, 400000, 380000, 360000, 370000,
                             350000, 340000, 360000, 370000, 355000, 360000],
    },
    {
        "merchant_id": "GRAB_M005", "category": "Home & Living",
        "monthly_revenue": 720000,  "credit_score": 750, "years_in_business": 8,
        "existing_loans": 0, "past_defaults": 0,
        "chargeback_rate": 0.006, "refund_rate": 0.02,
        "avg_order_value": 6200,  "unique_customer_count": 2800,
        "customer_return_rate": 0.51, "coupon_redemption_rate": 0.15,
        "seasonality_index": 1.4, "deal_exclusivity_rate": 0.35,
        "return_and_refund_rate": 0.02,
        # Consistent growth
        "monthly_gmv_12m": [680000, 695000, 700000, 710000, 720000, 730000,
                             725000, 740000, 750000, 760000, 755000, 770000],
    },
    {
        # TIER 3 REJECTED — very young, high loans, high chargeback, declining GMV
        "merchant_id": "GRAB_M006", "category": "Sports & Outdoors",
        "monthly_revenue": 290000,  "credit_score": 610, "years_in_business": 1,
        "existing_loans": 3, "past_defaults": 1,
        "chargeback_rate": 0.030, "refund_rate": 0.08,
        "avg_order_value": 3500,  "unique_customer_count": 650,
        "customer_return_rate": 0.15, "coupon_redemption_rate": 0.05,
        "seasonality_index": 1.8, "deal_exclusivity_rate": 0.05,
        "return_and_refund_rate": 0.08,
        # Declining — struggling merchant
        "monthly_gmv_12m": [350000, 330000, 320000, 300000, 290000, 280000,
                             270000, 285000, 290000, 275000, 270000, 260000],
    },
    {
        "merchant_id": "GRAB_M007", "category": "Toys & Games",
        "monthly_revenue": 510000,  "credit_score": 700, "years_in_business": 3,
        "existing_loans": 1, "past_defaults": 0,
        "chargeback_rate": 0.012, "refund_rate": 0.03,
        "avg_order_value": 1500,  "unique_customer_count": 4300,
        "customer_return_rate": 0.33, "coupon_redemption_rate": 0.20,
        "seasonality_index": 2.1, "deal_exclusivity_rate": 0.15,
        "return_and_refund_rate": 0.03,
        # Stable with strong Q4 seasonality (festive/holiday)
        "monthly_gmv_12m": [420000, 430000, 450000, 480000, 500000, 490000,
                             480000, 500000, 510000, 530000, 520000, 510000],
    },
    {
        "merchant_id": "GRAB_M008", "category": "Automotive",
        "monthly_revenue": 960000,  "credit_score": 780, "years_in_business": 10,
        "existing_loans": 0, "past_defaults": 0,
        "chargeback_rate": 0.004, "refund_rate": 0.01,
        "avg_order_value": 12000, "unique_customer_count": 900,
        "customer_return_rate": 0.67, "coupon_redemption_rate": 0.10,
        "seasonality_index": 1.0, "deal_exclusivity_rate": 0.60,
        "return_and_refund_rate": 0.01,
        # Strong sustained growth
        "monthly_gmv_12m": [900000, 910000, 920000, 930000, 940000, 950000,
                             960000, 970000, 975000, 980000, 990000, 1000000],
    },
    {
        "merchant_id": "GRAB_M009", "category": "Books & Stationery",
        "monthly_revenue": 175000,  "credit_score": 665, "years_in_business": 3,
        "existing_loans": 1, "past_defaults": 0,
        "chargeback_rate": 0.003, "refund_rate": 0.02,
        "avg_order_value": 450,   "unique_customer_count": 6700,
        "customer_return_rate": 0.44, "coupon_redemption_rate": 0.35,
        "seasonality_index": 1.3, "deal_exclusivity_rate": 0.10,
        "return_and_refund_rate": 0.02,
        # Stable with back-to-school seasonal spikes
        "monthly_gmv_12m": [160000, 165000, 170000, 175000, 180000, 175000,
                             170000, 165000, 170000, 175000, 178000, 180000],
    },
    {
        "merchant_id": "GRAB_M010", "category": "Jewellery",
        "monthly_revenue": 1100000, "credit_score": 800, "years_in_business": 12,
        "existing_loans": 0, "past_defaults": 0,
        "chargeback_rate": 0.002, "refund_rate": 0.01,
        "avg_order_value": 18000, "unique_customer_count": 1500,
        "customer_return_rate": 0.72, "coupon_redemption_rate": 0.08,
        "seasonality_index": 1.5, "deal_exclusivity_rate": 0.70,
        "return_and_refund_rate": 0.01,
        # Premium category, strong growth
        "monthly_gmv_12m": [950000, 970000, 980000, 1000000, 1010000, 1020000,
                             1040000, 1050000, 1060000, 1080000, 1090000, 1100000],
    },
]


def init_db():
    """Initialize database by creating all tables, then seed sample merchants."""
    Base.metadata.create_all(bind=engine)
    _seed_merchants()


def _seed_merchants():
    """Insert or update the 10 fixed sample merchants."""
    db = SessionLocal()
    try:
        for data in SAMPLE_MERCHANTS:
            merchant = db.query(Merchant).filter_by(merchant_id=data["merchant_id"]).first()
            if not merchant:
                merchant = Merchant(merchant_id=data["merchant_id"])
                db.add(merchant)

            # Always sync fields so profile updates propagate on restart
            merchant.category               = data["category"]
            merchant.monthly_revenue        = data["monthly_revenue"]
            merchant.credit_score           = data["credit_score"]
            merchant.years_in_business      = data["years_in_business"]
            merchant.existing_loans         = data["existing_loans"]
            merchant.past_defaults          = data["past_defaults"]
            merchant.chargeback_rate        = data["chargeback_rate"]
            merchant.refund_rate            = data["refund_rate"]
            merchant.gmv                    = data["monthly_revenue"] * 1.2
            merchant.avg_order_value        = data["avg_order_value"]
            merchant.unique_customer_count  = data["unique_customer_count"]
            merchant.customer_return_rate   = data["customer_return_rate"]
            merchant.coupon_redemption_rate = data["coupon_redemption_rate"]
            merchant.seasonality_index      = data["seasonality_index"]
            merchant.deal_exclusivity_rate  = data["deal_exclusivity_rate"]
            merchant.return_and_refund_rate = data["return_and_refund_rate"]
            merchant.monthly_gmv_12m        = data["monthly_gmv_12m"]
            # Keep mobile_number if already set by admin
            if merchant.mobile_number is None:
                merchant.mobile_number = None

        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
    print("Database initialized successfully!")
