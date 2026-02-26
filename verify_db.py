from app.db.session import SessionLocal
from app.models.merchant import Merchant
from app.models.risk_score import RiskScore

db = SessionLocal()

print("=" * 80)
print("DATABASE VERIFICATION")
print("=" * 80)

print("\nMERCHANTS TABLE:")
print("-" * 80)
merchants = db.query(Merchant).all()
print(f"Total records: {len(merchants)}")
for m in merchants:
    print(f"  ID: {m.id}, Merchant: {m.merchant_id}, Revenue: {m.monthly_revenue}, Credit: {m.credit_score}, Loans: {m.existing_loans}, Defaults: {m.past_defaults}")

print("\nRISK_SCORES TABLE:")
print("-" * 80)
risk_scores = db.query(RiskScore).all()
print(f"Total records: {len(risk_scores)}")
for r in risk_scores:
    print(f"  ID: {r.id}, Merchant: {r.merchant_id}, Score: {r.risk_score}, Tier: {r.risk_tier}, Decision: {r.decision}")

print("\nVALIDATION:")
print("-" * 80)
print(f"✓ Merchants table populated: {len(merchants) > 0}")
print(f"✓ Risk scores table populated: {len(risk_scores) > 0}")
print(f"✓ Records match: {len(merchants) == len(risk_scores)}")

# Check for nulls
null_check = True
for m in merchants:
    if not m.merchant_id or m.monthly_revenue is None or m.credit_score is None:
        null_check = False
for r in risk_scores:
    if not r.merchant_id or r.risk_score is None or not r.risk_tier or not r.decision:
        null_check = False

print(f"✓ No null values in critical columns: {null_check}")
print("\n" + "=" * 80)

db.close()
