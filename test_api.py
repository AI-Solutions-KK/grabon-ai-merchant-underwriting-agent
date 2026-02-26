import requests
import json
import time

time.sleep(2)

test_cases = [
    {
        'name': 'Case 1 - Strong Merchant (Tier 1)',
        'data': {
            'merchant_id': 'PHASE3_TEST_M1',
            'monthly_revenue': 90000,
            'credit_score': 780,
            'years_in_business': 6,
            'existing_loans': 0,
            'past_defaults': 0
        },
        'expect': 'Tier 1'
    },
    {
        'name': 'Case 2 - Moderate Merchant (Tier 2)',
        'data': {
            'merchant_id': 'PHASE3_TEST_M2',
            'monthly_revenue': 40000,
            'credit_score': 680,
            'years_in_business': 3,
            'existing_loans': 2,
            'past_defaults': 0
        },
        'expect': 'Tier 2'
    },
    {
        'name': 'Case 3 - Auto Reject Low Credit (Tier 3)',
        'data': {
            'merchant_id': 'PHASE3_TEST_M3',
            'monthly_revenue': 50000,
            'credit_score': 520,
            'years_in_business': 5,
            'existing_loans': 1,
            'past_defaults': 0
        },
        'expect': 'Tier 3'
    },
    {
        'name': 'Case 4 - Auto Reject Many Defaults (Tier 3)',
        'data': {
            'merchant_id': 'PHASE3_TEST_M4',
            'monthly_revenue': 60000,
            'credit_score': 700,
            'years_in_business': 5,
            'existing_loans': 1,
            'past_defaults': 3
        },
        'expect': 'Tier 3'
    }
]

print('=' * 80)
print('PHASE 3 - MANUAL API TESTING (4 SCENARIOS)')
print('=' * 80)

passed = 0
failed = 0

for test in test_cases:
    try:
        response = requests.post('http://127.0.0.1:8000/api/underwrite', json=test['data'])
        result = response.json()
        
        print()
        print(f"TEST: {test['name']}")
        print(f"  Merchant ID: {result['merchant_id']}")
        print(f"  Risk Score: {result['risk_score']}/100")
        print(f"  Risk Tier: {result['risk_tier']:<10} (Expected: {test['expect']})")
        print(f"  Decision: {result['decision']}")
        print(f"  Explanation: {result['explanation'][:75]}...")
        
        if result['risk_tier'] == test['expect']:
            print(f"  PASS: Correct tier")
            passed += 1
        else:
            print(f"  FAIL: Expected {test['expect']}, got {result['risk_tier']}")
            failed += 1
    except Exception as e:
        print()
        print(f"ERROR in {test['name']}: {e}")
        failed += 1

print()
print('=' * 80)
print(f'RESULTS: {passed} PASSED, {failed} FAILED (Total: {len(test_cases)})')
print('=' * 80)
if passed == len(test_cases):
    print('SUCCESS: All test cases passed!')
else:
    print(f'FAILURE: {failed} test(s) failed')
