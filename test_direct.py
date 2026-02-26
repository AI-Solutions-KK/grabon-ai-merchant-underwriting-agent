#!/usr/bin/env python3
"""
Direct API test - imports the app directly to test
Tests Phase 4: Claude Integration
"""

import os
import sys
import asyncio
from typing import Dict, Any

# Setup path
sys.path.insert(0, '/mnt/c/MyFiles/My_Projects/grabon-assignment')

# Test merchants
TEST_MERCHANTS = {
    "strong": {
        "merchant_id": "STRONG_001",
        "monthly_revenue": 50000,
        "credit_score": 780,
        "years_in_business": 5,
        "existing_loans": 1,
        "past_defaults": 0
    },
    "moderate": {
        "merchant_id": "MOD_001",
        "monthly_revenue": 15000,
        "credit_score": 680,
        "years_in_business": 2,
        "existing_loans": 2,
        "past_defaults": 0
    },
    "low_credit": {
        "merchant_id": "LOW_001",
        "monthly_revenue": 20000,
        "credit_score": 540,  # REJECTED - below 550
        "years_in_business": 3,
        "existing_loans": 0,
        "past_defaults": 0
    },
    "high_defaults": {
        "merchant_id": "HIGH_001",
        "monthly_revenue": 30000,
        "credit_score": 700,
        "years_in_business": 4,
        "existing_loans": 2,
        "past_defaults": 3  # REJECTED - above 2
    }
}

def test_orchestrator():
    """Test orchestrator directly"""
    from app.orchestrator.orchestrator import Orchestrator
    from app.db.session import SessionLocal, engine
    from app.db.base import Base
    from app.models.merchant import Merchant
    from app.models.risk_score import RiskScore
    from app.schemas.merchant_schema import MerchantInput
    from sqlalchemy.orm import Session
    
    # Initialize DB
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    # Create session
    db = SessionLocal()
    orchestrator = Orchestrator()
    
    print("="*70)
    print("PHASE 4: DIRECT ORCHESTRATOR TEST")
    print("="*70)
    
    results = []
    for merchant_name, merchant_data in TEST_MERCHANTS.items():
        print(f"\nTesting: {merchant_name}")
        print(f"  Merchant ID: {merchant_data['merchant_id']}")
        print(f"  Credit: {merchant_data['credit_score']}, Revenue: ${merchant_data['monthly_revenue']:,}")
        
        try:
            # Convert dict to MerchantInput
            merchant_input = MerchantInput(**merchant_data)
            decision = orchestrator.process_underwriting(merchant_input, db)
            
            print(f"  [OK] Decision: {decision.decision}")
            print(f"       Risk Tier: {decision.risk_tier}")
            print(f"       Risk Score: {decision.risk_score}")
            print(f"       Explanation: {decision.explanation[:80]}...")
            
            # Check explanation quality
            exp = decision.explanation
            has_detail = len(exp) > 80
            has_metrics = any(w in exp.lower() for w in ["credit", "revenue", "business", "score"])
            
            passed = has_detail and has_metrics
            results.append({
                "merchant": merchant_name,
                "passed": passed,
                "decision": decision.decision,
                "explanation": exp
            })
            
            print(f"       [Detail={has_detail}] [Metrics={has_metrics}]")
            
        except Exception as e:
            print(f"  [ERROR] {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            results.append({
                "merchant": merchant_name,
                "error": str(e)
            })
    
    # Summary
    print("\n" + "="*70)
    passed = sum(1 for r in results if r.get("passed", False))
    print(f"RESULTS: {passed}/{len(TEST_MERCHANTS)} merchants passed")
    
    for r in results:
        status = "[PASS]" if r.get("passed") else "[FAIL]"
        print(f"  {status} {r['merchant']}: {r.get('decision', 'ERROR')}")
    
    # Test with broken API key
    print("\n" + "="*70)
    print("TESTING FALLBACK WITH BROKEN API KEY")
    print("="*70)
    
    os.environ["ANTHROPIC_API_KEY"] = "fake_key_invalid"
    
    merchant = TEST_MERCHANTS["strong"]
    try:
        merchant_input = MerchantInput(**merchant)
        decision = orchestrator.process_underwriting(merchant_input, db)
        has_fallback = "merchant" in decision.explanation.lower() or "classified" in decision.explanation.lower()
        print(f"[OK] Fallback worked")
        print(f"     Decision: {decision.decision}")
        print(f"     Is fallback: {has_fallback}")
        print(f"     Explanation: {decision.explanation}")
    except Exception as e:
        print(f"[ERROR] Fallback failed: {e}")
        import traceback
        traceback.print_exc()
    
    db.close()
    print("="*70 + "\n")

if __name__ == "__main__":
    print("\nPHASE 4: DIRECT APP TEST")
    try:
        test_orchestrator()
        print("[SUCCESS] Phase 4 testing complete")
    except Exception as e:
        print(f"[FAILED] {e}")
        import traceback
        traceback.print_exc()
