"""
STEP C: Live WhatsApp Production Validation Test

Tests the full underwriting flow with real WhatsApp delivery.
Uses a test merchant and validates message delivery.
"""

import sys
sys.path.insert(0, '.')

from app.orchestrator.orchestrator import Orchestrator
from app.db.session import SessionLocal
from app.schemas.merchant_schema import MerchantInput
from dotenv import load_dotenv
import os

load_dotenv()

def test_whatsapp_delivery():
    """Test live WhatsApp delivery with real phone number"""
    
    print("\n" + "=" * 80)
    print("STEP C: LIVE WHATSAPP PRODUCTION VALIDATION")
    print("=" * 80 + "\n")
    
    # Test merchant
    test_merchant = MerchantInput(
        merchant_id="WHATSAPP_TEST_001",
        monthly_revenue=75000,
        credit_score=750,
        years_in_business=5,
        existing_loans=1,
        past_defaults=0,
        gmv=100000,
        refund_rate=0.05,
        chargeback_rate=0.02
    )
    
    db = SessionLocal()
    orchestrator = Orchestrator()
    
    # User's real phone number
    whatsapp_number = "whatsapp:+918999980406"
    
    print(f"📱 Testing with your real phone: {whatsapp_number}")
    print(f"🎯 Merchant: {test_merchant.merchant_id}")
    print(f"💰 Revenue: ${test_merchant.monthly_revenue/1000:.0f}k/month")
    print()
    
    try:
        print("[1/3] Processing underwriting...")
        decision = orchestrator.process_underwriting(test_merchant, db, whatsapp_number)
        
        print(f"[2/3] Decision made:")
        print(f"  ✅ Tier: {decision.risk_tier}")
        print(f"  ✅ Decision: {decision.decision}")
        print(f"  ✅ Score: {decision.risk_score}/100")
        
        print(f"\n[3/3] Checking WhatsApp delivery...")
        print(f"  📤 Message sent to: {whatsapp_number}")
        print(f"  ℹ️  Check your phone for message from Twilio Sandbox")
        print(f"  ℹ️  Expected format: Emoji header + merchant info + explanation + footer")
        
        print("\n" + "=" * 80)
        print("✅ TEST COMPLETE")
        print("=" * 80)
        print("\nIf you received the message:")
        print("  ✅ WhatsApp integration is WORKING")
        print("  ✅ API response is valid")
        print("  ✅ Claude explanation was generated")
        print("  ✅ Message formatting is correct")
        print("\nIf you did NOT receive the message:")
        print("  ⚠️  Check Twilio credentials in .env")
        print("  ⚠️  Verify phone number is correct")
        print("  ⚠️  Ensure Twilio Sandbox is joined")
        print("  ⚠️  Check application logs for errors")
        print("\n" + "=" * 80 + "\n")
        
        db.close()
        
    except Exception as e:
        print(f"\n❌ ERROR during test: {str(e)}")
        import traceback
        traceback.print_exc()
        db.close()
        return False
    
    return True

if __name__ == "__main__":
    success = test_whatsapp_delivery()
    sys.exit(0 if success else 1)
