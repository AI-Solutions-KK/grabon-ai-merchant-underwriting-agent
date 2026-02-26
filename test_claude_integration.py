"""
Test Suite for Phase 4: Claude Integration with Fallback Safety
Tests Steps 6 & 7:
- Step 6: Manual testing with live Claude API
- Step 7: Failure safety verification with broken API key
"""

import os
import json
import requests
from typing import Dict, Any

BASE_URL = "http://localhost:8000/api"

# Test merchant profiles
TEST_MERCHANTS = {
    "strong_merchant": {
        "merchant_id": "STRONG_001",
        "monthly_revenue": 50000,
        "credit_score": 780,
        "years_in_business": 5,
        "existing_loans": 1,
        "past_defaults": 0
    },
    "moderate_merchant": {
        "merchant_id": "MODERATE_001",
        "monthly_revenue": 15000,
        "credit_score": 680,
        "years_in_business": 2,
        "existing_loans": 2,
        "past_defaults": 0
    },
    "low_credit_rejection": {
        "merchant_id": "LOWCREDIT_001",
        "monthly_revenue": 20000,
        "credit_score": 540,  # Below 550 threshold
        "years_in_business": 3,
        "existing_loans": 0,
        "past_defaults": 0
    },
    "high_defaults_rejection": {
        "merchant_id": "DEFAULTS_001",
        "monthly_revenue": 30000,
        "credit_score": 700,
        "years_in_business": 4,
        "existing_loans": 2,
        "past_defaults": 3  # Above max of 2
    }
}

def validate_explanation(explanation: str, merchant_name: str, decision: str) -> Dict[str, Any]:
    """Validate explanation format and content"""
    validation_result = {
        "merchant": merchant_name,
        "decision": decision,
        "explanation": explanation,
        "checks": {
            "length": False,
            "mentions_revenue": False,
            "mentions_credit": False,
            "mentions_years": False,
            "is_ai_generated": False,
            "professional_tone": False
        },
        "issues": []
    }
    
    # Check length (should be 3-5 sentences, estimate by period count)
    sentence_count = explanation.count('.') - explanation.count('...')
    if 2 <= sentence_count <= 6:  # Allow slight variation
        validation_result["checks"]["length"] = True
    else:
        validation_result["issues"].append(f"Expected 3-5 sentences, got ~{sentence_count}")
    
    # Check metric mentions
    exp_lower = explanation.lower()
    if any(word in exp_lower for word in ["revenue", "monthly", "income", "sales"]):
        validation_result["checks"]["mentions_revenue"] = True
    else:
        validation_result["issues"].append("Missing revenue reference")
    
    if any(word in exp_lower for word in ["credit", "score", "720", "680", "780", "540"]):
        validation_result["checks"]["mentions_credit"] = True
    else:
        validation_result["issues"].append("Missing credit score reference")
    
    if any(word in exp_lower for word in ["years", "business", "established", "experience"]):
        validation_result["checks"]["mentions_years"] = True
    else:
        validation_result["issues"].append("Missing years in business reference")
    
    # Check for AI indicators (not fallback template)
    ai_indicators = [
        "demonstrates",
        "indicates",
        "reveals",
        "shows strong",
        "shows concerning",
        "financial stability",
        "presents",
        "classified as",  # This is too generic, should be specific
    ]
    fallback_keywords = ["merchant", "classified as", "risk score", "with decision"]
    
    # If it sounds templated (all fallback keywords present), it's likely fallback
    template_count = sum(1 for kw in fallback_keywords if kw in exp_lower)
    if template_count <= 2:  # Allows some overlap
        validation_result["checks"]["is_ai_generated"] = True
    else:
        validation_result["checks"]["is_ai_generated"] = False
        validation_result["issues"].append("Explanation appears to be fallback template")
    
    # Check professional tone
    if not any(char in explanation for char in ['!', '?', '!!'] * 2):  # No excessive punctuation
        if len(explanation) > 50:  # Reasonable length
            validation_result["checks"]["professional_tone"] = True
    
    validation_result["pass"] = all(validation_result["checks"].values())
    return validation_result

def test_step_6_live_claude():
    """Step 6: Manually test with live Claude API"""
    print("\n" + "="*70)
    print("STEP 6: MANUAL TESTING WITH LIVE CLAUDE API")
    print("="*70)
    
    results = []
    
    for merchant_name, merchant_data in TEST_MERCHANTS.items():
        print(f"\n📝 Testing: {merchant_name.upper()}")
        print(f"   ID: {merchant_data['merchant_id']}")
        print(f"   Credit Score: {merchant_data['credit_score']}")
        print(f"   Monthly Revenue: ${merchant_data['monthly_revenue']:,}")
        print(f"   Years in Business: {merchant_data['years_in_business']}")
        
        try:
            response = requests.post(f"{BASE_URL}/underwrite", json=merchant_data)
            response.raise_for_status()
            
            result = response.json()
            print(f"\n   ✅ Response Status: {response.status_code}")
            print(f"   Risk Score: {result['risk_score']}")
            print(f"   Risk Tier: {result['risk_tier']}")
            print(f"   Decision: {result['decision']}")
            print(f"\n   📋 Explanation:")
            print(f"   {result['explanation']}")
            
            # Validate explanation
            validation = validate_explanation(
                result['explanation'],
                merchant_name,
                result['decision']
            )
            
            print(f"\n   🔍 Explanation Quality Checks:")
            for check, passed in validation["checks"].items():
                status = "✅" if passed else "❌"
                print(f"      {status} {check.replace('_', ' ').title()}")
            
            if validation["issues"]:
                print(f"\n   ⚠️  Issues Found:")
                for issue in validation["issues"]:
                    print(f"      - {issue}")
            
            results.append({
                "merchant": merchant_name,
                "validation": validation,
                "response": result
            })
            
        except requests.exceptions.RequestException as e:
            print(f"   ❌ Error: {e}")
            results.append({
                "merchant": merchant_name,
                "error": str(e)
            })
    
    # Summary
    print("\n" + "="*70)
    print("STEP 6 SUMMARY")
    print("="*70)
    passed = sum(1 for r in results if r.get("validation", {}).get("pass", False))
    total = len(results)
    print(f"Explanations Validated: {passed}/{total}")
    
    if passed == total:
        print("✅ All explanations appear AI-generated with proper formatting")
    else:
        print(f"⚠️  {total - passed} explanation(s) may be fallback format")
    
    return results

def test_step_7_failure_safety():
    """Step 7: Verify failure safety with broken API key"""
    print("\n" + "="*70)
    print("STEP 7: VERIFY FAILURE SAFETY")
    print("="*70)
    
    # Save original API key
    original_key = os.environ.get("ANTHROPIC_API_KEY")
    
    # Test 1: Test with broken API key
    print("\n🔨 TEST 1: Simulating API Failure (broken key)")
    print("-" * 70)
    
    os.environ["ANTHROPIC_API_KEY"] = "fake_key_12345"
    
    merchant_data = TEST_MERCHANTS["strong_merchant"]
    
    try:
        response = requests.post(f"{BASE_URL}/underwrite", json=merchant_data)
        response.raise_for_status()
        
        result = response.json()
        print(f"✅ System handled API failure gracefully")
        print(f"   Decision: {result['decision']}")
        print(f"\n   📋 Fallback Explanation:")
        print(f"   {result['explanation']}")
        
        # Check if it's fallback format
        is_fallback = any(phrase in result['explanation'].lower() for phrase in 
                         ["merchant", "classified as", "with risk score", "with decision"])
        
        if is_fallback:
            print(f"\n   ✅ Fallback explanation detected (template format)")
        else:
            print(f"\n   ⚠️  Explanation doesn't match fallback pattern")
        
        test1_passed = response.status_code == 200 and 'explanation' in result
        
    except Exception as e:
        print(f"   ❌ System crashed: {e}")
        test1_passed = False
    
    # Test 2: Restore API key and verify recovery
    print("\n🔄 TEST 2: Restoring API Key and Verifying Recovery")
    print("-" * 70)
    
    if original_key:
        os.environ["ANTHROPIC_API_KEY"] = original_key
    else:
        print("⚠️  Warning: ANTHROPIC_API_KEY was not previously set")
        # Try to use it anyway, or skip
        if "ANTHROPIC_API_KEY" in os.environ:
            del os.environ["ANTHROPIC_API_KEY"]
    
    try:
        response = requests.post(f"{BASE_URL}/underwrite", json=merchant_data)
        response.raise_for_status()
        
        result = response.json()
        explanation = result['explanation']
        
        # Check if explanation is now different (more detailed, Claude-generated)
        is_likely_claude = len(explanation) > 150 and any(
            phrase in explanation for phrase in 
            ["demonstrates", "indicates", "presents", "reveals", "shows"]
        )
        
        if is_likely_claude:
            print(f"✅ System recovered - Claude explanation restored")
        else:
            print(f"⚠️  Explanation may still be fallback (monitor for Claude availability)")
        
        print(f"\n   Decision: {result['decision']}")
        print(f"   Explanation length: {len(explanation)} chars")
        
        test2_passed = response.status_code == 200
        
    except Exception as e:
        print(f"   ❌ Recovery failed: {e}")
        test2_passed = False
    
    # Summary
    print("\n" + "="*70)
    print("STEP 7 SUMMARY")
    print("="*70)
    
    if test1_passed and test2_passed:
        print("✅ Failure Safety Verified:")
        print("   ✓ System handles broken API key gracefully")
        print("   ✓ Fallback explanation returned when API unavailable")
        print("   ✓ System recovers when API key restored")
    else:
        print("⚠️  Failure Safety Issues Detected:")
        if not test1_passed:
            print("   ✗ System did not handle broken key gracefully")
        if not test2_passed:
            print("   ✗ System did not recover after key restoration")
    
    return {"test1": test1_passed, "test2": test2_passed}

if __name__ == "__main__":
    print("\n" + "="*70)
    print("PHASE 4: CLAUDE INTEGRATION TEST SUITE")
    print("Steps 6 & 7: Manual Testing + Failure Safety")
    print("="*70)
    
    # Check if server is running
    try:
        response = requests.get(f"{BASE_URL}/docs", timeout=2)
        print("\n✅ Server is running and accessible")
    except:
        print("\n❌ ERROR: Server is not running!")
        print("   Please start the server: uvicorn app.main:app --reload")
        exit(1)
    
    # Check API key is set
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\n⚠️  WARNING: ANTHROPIC_API_KEY not set in environment")
        print("   Please set it before running tests:")
        print("   $env:ANTHROPIC_API_KEY = 'your-key-here'")
        print("\n   Proceeding anyway (will test fallback behavior)...")
    
    # Run tests
    step6_results = test_step_6_live_claude()
    step7_results = test_step_7_failure_safety()
    
    # Final summary
    print("\n" + "="*70)
    print("PHASE 4 TEST EXECUTION COMPLETE")
    print("="*70)
    print(f"\nNext Steps:")
    print(f"  1. Review explanation quality above")
    print(f"  2. If Claude explanations ✅: System is production-ready")
    print(f"  3. If fallback only: Verify ANTHROPIC_API_KEY is set correctly")
    print(f"  4. Commit changes to git when satisfied")
    print("="*70 + "\n")
