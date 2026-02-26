from sqlalchemy.orm import Session
from app.models.merchant import Merchant
from app.schemas.merchant_schema import MerchantInput


class MerchantService:
    """
    Service layer for merchant data operations.
    
    Handles persistence of merchant information to the database.
    """
    
    @staticmethod
    def create_merchant(db: Session, merchant_input: MerchantInput) -> Merchant:
        """
        Create and persist a merchant record.
        
        Args:
            db: SQLAlchemy database session
            merchant_input: MerchantInput schema with merchant data
            
        Returns:
            Merchant: Created merchant record
        """
        db_merchant = Merchant(
            merchant_id=merchant_input.merchant_id,
            monthly_revenue=merchant_input.monthly_revenue,
            credit_score=merchant_input.credit_score,
            years_in_business=merchant_input.years_in_business,
            existing_loans=merchant_input.existing_loans,
            past_defaults=merchant_input.past_defaults
        )
        db.add(db_merchant)
        db.commit()
        db.refresh(db_merchant)
        return db_merchant
    
    @staticmethod
    def get_by_merchant_id(db: Session, merchant_id: str) -> Merchant:
        """
        Retrieve a merchant by merchant_id.
        
        Args:
            db: SQLAlchemy database session
            merchant_id: Unique merchant identifier
            
        Returns:
            Merchant: Merchant record if found, None otherwise
        """
        return db.query(Merchant).filter(Merchant.merchant_id == merchant_id).first()
