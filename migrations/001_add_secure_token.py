"""
Migration: Add secure_token to existing merchants (one-time).

This script assigns UUID tokens to merchants that don't have one yet.
"""

from app.db.session import SessionLocal
from app.models.merchant import Merchant
from uuid import uuid4


def migrate_add_secure_tokens():
    """
    One-time migration to add secure_token to existing merchants.
    
    Updates all merchants where secure_token is NULL.
    """
    db = SessionLocal()
    
    try:
        # Find merchants without secure_token
        merchants_without_token = db.query(Merchant).filter(
            Merchant.secure_token == None
        ).all()
        
        if not merchants_without_token:
            print("✓ All merchants already have secure_token assigned.")
            return
        
        print(f"Found {len(merchants_without_token)} merchants without secure_token.")
        print("Assigning UUID tokens...")
        
        for merchant in merchants_without_token:
            merchant.secure_token = str(uuid4())
            print(f"  • {merchant.merchant_id} → {merchant.secure_token}")
        
        # Commit all changes
        db.commit()
        
        print(f"\n✓ Successfully assigned tokens to {len(merchants_without_token)} merchants.")
        
    except Exception as e:
        print(f"✗ Error during migration: {e}")
        db.rollback()
        
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 70)
    print("MIGRATION: Add secure_token to existing merchants")
    print("=" * 70)
    print()
    
    migrate_add_secure_tokens()
