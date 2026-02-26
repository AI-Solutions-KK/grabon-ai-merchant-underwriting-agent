"""
Production seeding script: 10 merchants with realistic distribution.

Distribution:
- Tier 1 (APPROVED): 3 merchants with high credit (760+), high revenue (80k+)
- Tier 2 (APPROVED_WITH_CONDITIONS): 3 merchants with mid credit (650-720), mid revenue (30k-60k)
- Tier 3 (REJECTED): 2 merchants with poor metrics
- Auto-Reject: 2 merchants with hard failures (credit < 550 OR defaults >= 3)
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.db.session import SessionLocal
from app.db.base import Base
from app.db.session import engine
from app.models.merchant import Merchant
from app.models.risk_score import RiskScore
from app.orchestrator.orchestrator import Orchestrator
from app.schemas.merchant_schema import MerchantInput
from dotenv import load_dotenv

load_dotenv()

def seed_merchants():
    """Seed 10 merchants with realistic distribution."""
    
    # Merchant configurations: (id, name, monthly_revenue, credit_score, years, loans, defaults, gmv, refund_rate, chargeback_rate)
    merchants_config = [
        # TIER 1 - APPROVED (high credit, high revenue, 0 defaults)
        ("PROD_T1_001", "Premium Fintech Solutions", 120000, 795, 8, 0, 0, 180000, 0.02, 0.01),  # Excellent metrics
        ("PROD_T1_002", "Elite Retail Group", 95000, 780, 6, 1, 0, 150000, 0.03, 0.02),  # Low refund/chargeback
        ("PROD_T1_003", "Established Services Inc", 110000, 765, 7, 0, 0, 160000, 0.04, 0.015),  # Good metrics
        
        # TIER 2 - APPROVED_WITH_CONDITIONS (mid credit, mid revenue)
        ("PROD_T2_001", "Growing Tech Startup", 50000, 715, 4, 2, 0, 75000, 0.08, 0.03),  # Moderate refund
        ("PROD_T2_002", "Mid-Market Retail Co", 45000, 690, 3, 3, 1, 60000, 0.12, 0.05),  # Elevated concerns
        ("PROD_T2_003", "Development Agency", 60000, 700, 5, 1, 0, 85000, 0.06, 0.025),  # Below-average refund
        
        # TIER 3 - REJECTED (low revenue, multiple issues)
        ("PROD_T3_001", "Early Stage Platform", 15000, 640, 1, 4, 2, 20000, 0.25, 0.08),  # High refund
        ("PROD_T3_002", "Struggling Service Co", 20000, 630, 2, 5, 1, 25000, 0.35, 0.12),  # Very high refund/chargeback
        
        # AUTO-REJECT - MANDATORY FAILURES
        ("PROD_AR_001", "Borderline Bad Credit", 30000, 545, 3, 0, 0, 40000, 0.05, 0.02),  # Credit < 550
        ("PROD_AR_002", "Default Heavy Vendor", 25000, 600, 2, 2, 3, 35000, 0.40, 0.15),   # Defaults >= 3, plus high risk metrics
    ]
    
    # Database session
    db = SessionLocal()
    orchestrator = Orchestrator()
    
    print("\n" + "=" * 80)
    print("PRODUCTION SEEDING: 10 MERCHANTS")
    print("=" * 80 + "\n")
    
    try:
        for merchant_id, merchant_name, revenue, credit, years, loans, defaults, gmv, refund_rate, chargeback_rate in merchants_config:
            print(f"[SEEDING] {merchant_id}: {merchant_name}")
            
            # Create merchant input
            merchant_input = MerchantInput(
                merchant_id=merchant_id,
                monthly_revenue=revenue,
                credit_score=credit,
                years_in_business=years,
                existing_loans=loans,
                past_defaults=defaults,
                gmv=gmv,
                refund_rate=refund_rate,
                chargeback_rate=chargeback_rate
            )
            
            # Process through orchestrator for full evaluation
            try:
                decision = orchestrator.process_underwriting(merchant_input, db)
                
                status_marker = "✅"
                print(f"  {status_marker} {decision.risk_tier} | {decision.decision} | Score: {decision.risk_score}")
                
            except Exception as e:
                print(f"  ❌ ERROR: {str(e)}")
                db.rollback()
        
        db.close()
        
        # Print summary
        print("\n" + "=" * 80)
        db = SessionLocal()
        merchants_count = db.query(Merchant).count()
        print(f"SEEDING COMPLETE: {merchants_count} merchants loaded")
        print("=" * 80 + "\n")
        
        # Show distribution
        risk_scores = db.query(RiskScore).all()
        
        tier1 = [r for r in risk_scores if r.risk_tier == "Tier 1"]
        tier2 = [r for r in risk_scores if r.risk_tier == "Tier 2"]
        tier3 = [r for r in risk_scores if r.risk_tier == "Tier 3"]
        auto_reject = [r for r in risk_scores if r.decision == "AUTO_REJECTED"]
        
        print(f"📊 DISTRIBUTION:")
        print(f"   Tier 1 (APPROVED):              {len(tier1)}")
        print(f"   Tier 2 (APPROVED_WITH_CONDITIONS): {len(tier2)}")
        print(f"   Tier 3 (REJECTED):              {len(tier3)}")
        print(f"   Auto-Reject (Hard Failures):    {len(auto_reject)}")
        print()
        
        db.close()
        
    except Exception as e:
        print(f"FATAL ERROR: {str(e)}")
        db.rollback()
        db.close()
        raise

if __name__ == "__main__":
    seed_merchants()
