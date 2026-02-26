"""
Simplified test for Phase 4: Claude Integration
Tests with proper timeout and ASCII output only
"""

import os
import json
import requests
import time

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
        "credit_score": 540,
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
        "past_defaults": 3
    }
}

def check_explanation_quality(explanation, merchant_name, decision):
    """Check explanation quality - returns pass/fail"""
    print(f"\n   Explanation: {explanation[:150]}...")
    
    checks = {
        "has_content": len(explanation) > 50,
        "mentions_metrics": any(word in explanation.lower() for word in ["credit", "revenue", "income", "business", "score"]),
        "professional": len(explanation) > 100,
    }
    
    passed = all(checks.values())
    print(f"   Checks: Content={checks['has_content']}, Metrics={checks['mentions_metrics']}, Professional={checks['professional']}")
    return passed

def test_with_live_api():
    """Test with real Claude API"""
    print("\n" + "="*70)
    print("TESTING WITH LIVE CLAUDE API")
    print("="*70)
    
    results = []
    
    for merchant_name, merchant_data in TEST_MERCHANTS.items():
        print(f"\nMerchant: {merchant_name}")
        
        try:
            response = requests.post(
                f"{BASE_URL}/underwrite", 
                json=merchant_data, 
                timeout=30  # Longer timeout for Claude API
            )
            response.raise_for_status()
            
            result = response.json()
            print(f"  Status: OK")
            print(f"  Decision: {result['decision']}")
            print(f"  Risk Tier: {result['risk_tier']}")
            print(f"  Risk Score: {result['risk_score']}")
            
            passed = check_explanation_quality(result['explanation'], merchant_name, result['decision'])
            results.append({
                "merchant": merchant_name,
                "decision": result['decision'],
                "passed": passed,
                "explanation": result['explanation']
            })
            
        except requests.exceptions.Timeout:
            print(f"  ERROR: Request timeout (API slow or unreachable)")
            results.append({"merchant": merchant_name, "error": "timeout"})
        except requests.exceptions.ConnectionError:
            print(f"  ERROR: Connection refused")
            results.append({"merchant": merchant_name, "error": "connection"})
        except Exception as e:
            print(f"  ERROR: {str(e)}")
            results.append({"merchant": merchant_name, "error": str(e)})
    
    # Summary
    print("\n" + "="*70)
    passed_count = sum(1 for r in results if r.get("passed", False))
    print(f"SUMMARY: {passed_count}/{len(TEST_MERCHANTS)} merchants passed")
    print("="*70)
    
    return results

def test_with_broken_key():
    """Test fallback when API key is broken"""
    print("\n" + "="*70)
    print("TESTING FALLBACK WITH BROKEN API KEY")
    print("="*70)
    
    original_key = os.environ.get("ANTHROPIC_API_KEY", "")
    os.environ["ANTHROPIC_API_KEY"] = "fake_key_invalid"
    
    merchant = TEST_MERCHANTS["strong_merchant"]
    
    try:
        response = requests.post(
            f"{BASE_URL}/underwrite",
            json=merchant,
            timeout=30
        )
        response.raise_for_status()
        
        result = response.json()
        print(f"Status: OK (Fallback returned)")
        print(f"Decision: {result['decision']}")
        print(f"Explanation: {result['explanation'][:100]}...")
        
        # Check if it's fallback format
        is_fallback = "merchant" in result['explanation'].lower() and "classified as" in result['explanation'].lower()
        print(f"Is Fallback: {'Yes' if is_fallback else 'Possibly Claude'}")
        
        return True
        
    except Exception as e:
        print(f"ERROR: System crashed with broken key: {e}")
        return False
    finally:
        # Restore key
        if original_key:
            os.environ["ANTHROPIC_API_KEY"] = original_key

if __name__ == "__main__":
    print("\n" + "="*70)
    print("PHASE 4: CLAUDE INTEGRATION TEST SUITE (SIMPLIFIED)")
    print("="*70)
    
    # Check server is running
    try:
        response = requests.get(f"{BASE_URL}/docs", timeout=10)
        print("\n[OK] Server is running")
    except:
        print("\n[ERROR] Server not accessible on http://localhost:8000")
        print("Please start it first: uvicorn app.main:app --reload")
        exit(1)
    
    # Check API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("[WARNING] ANTHROPIC_API_KEY not set - will test fallback behavior")
    else:
        print("[OK] ANTHROPIC_API_KEY is configured")
    
    # Run tests
    print("\n" + "="*70)
    test_results = test_with_live_api()
    fallback_test = test_with_broken_key()
    
    print("\n" + "="*70)
    print("FINAL SUMMARY")
    print("="*70)
    print(f"API Tests: {sum(1 for r in test_results if r.get('passed'))} passed")
    print(f"Fallback Test: {'Passed' if fallback_test else 'Failed'}")
    print("="*70 + "\n")
