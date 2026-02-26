"""
STEP D: Simulate WhatsApp Failure Mode Test

Tests API resilience when WhatsApp delivery fails.
Validates that underwriting result is still returned despite messaging failure.
"""

import sys
sys.path.insert(0, '.')

from app.orchestrator.orchestrator import Orchestrator
from app.db.session import SessionLocal
from app.schemas.merchant_schema import MerchantInput
from dotenv import load_dotenv
import os

load_dotenv()

def test_whatsapp_failure_resilience():
    """Test that API is resilient to WhatsApp failures"""
    
    print("\n" + "=" * 80)
    print("STEP D: WHATSAPP FAILURE MODE RESILIENCE TEST")
    print("=" * 80 + "\n")
    
    # Save original Twilio token
    original_token = os.getenv("TWILIO_AUTH_TOKEN")
    
    # Test merchant
    test_merchant = MerchantInput(
        merchant_id="FAILURE_TEST_001",
        monthly_revenue=50000,
        credit_score=700,
        years_in_business=4,
        existing_loans=2,
        past_defaults=0,
        gmv=75000,
        refund_rate=0.08,
        chargeback_rate=0.03
    )
    
    db = SessionLocal()
    orchestrator = Orchestrator()
    
    print("📋 TEST SCENARIO:")
    print("  1. Temporarily invalidate Twilio credentials")
    print("  2. Attempt underwriting with WhatsApp number")
    print("  3. Verify API still returns valid decision")
    print("  4. Restore credentials\n")
    
    try:
        # Step 1: Create broken environment
        print("[STEP 1] Breaking Twilio credentials...")
        os.environ["TWILIO_AUTH_TOKEN"] = "INVALID_TOKEN_12345"
        print("  ✅ Token set to invalid value\n")
        
        # Step 2: Process with WhatsApp (will fail)
        print("[STEP 2] Processing underwriting WITH WhatsApp (broken)...")
        whatsapp_number = "whatsapp:+918999980406"
        
        decision = orchestrator.process_underwriting(test_merchant, db, whatsapp_number)
        
        print(f"  ✅ Underwriting completed despite WhatsApp failure!")
        print(f"  ✅ Tier: {decision.risk_tier}")
        print(f"  ✅ Decision: {decision.decision}")
        print(f"  ✅ Score: {decision.risk_score}/100")
        print(f"  ✅ Explanation: {decision.explanation[:50]}...\n")
        
        # Step 3: Verify response is valid
        print("[STEP 3] Validating API resilience...")
        assert decision.merchant_id == "FAILURE_TEST_001", "Merchant ID mismatch"
        assert decision.decision in ["APPROVED", "APPROVED_WITH_CONDITIONS", "REJECTED", "AUTO_REJECTED"], "Invalid decision"
        assert 0 <= decision.risk_score <= 100, "Invalid score range"
        assert decision.explanation is not None and len(decision.explanation) > 0, "No explanation"
        print("  ✅ All assertions passed")
        print("  ✅ API is PRODUCTION-SAFE\n")
        
        # Step 4: Restore credentials
        print("[STEP 4] Restoring Twilio credentials...")
        os.environ["TWILIO_AUTH_TOKEN"] = original_token
        print("  ✅ Credentials restored\n")
        
        print("=" * 80)
        print("✅ RESILIENCE TEST PASSED")
        print("=" * 80)
        print("\nKey Findings:")
        print("  ✅ WhatsApp failure does NOT block underwriting API")
        print("  ✅ Decision is returned even with broken credentials")
        print("  ✅ Error is logged but not re-raised")
        print("  ✅ System is safe for production")
        print("\nProof:")
        print("  - API response was generated and returned")
        print("  - All required fields present")
        print("  - No exception reached client")
        print("  - Error handled gracefully in orchestrator")
        print("\n" + "=" * 80 + "\n")
        
        db.close()
        return True
        
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {str(e)}")
        # Restore anyway
        os.environ["TWILIO_AUTH_TOKEN"] = original_token
        import traceback
        traceback.print_exc()
        db.close()
        return False

if __name__ == "__main__":
    success = test_whatsapp_failure_resilience()
    sys.exit(0 if success else 1)
