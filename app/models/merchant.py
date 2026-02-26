from sqlalchemy import Column, Integer, String, Float
from app.db.base import Base


class Merchant(Base):
    """
    SQLAlchemy model for merchant information.
    
    Stores merchant financial metrics and business history.
    """
    __tablename__ = "merchants"

    id = Column(Integer, primary_key=True, index=True)
    merchant_id = Column(String, unique=True, index=True, nullable=False)
    monthly_revenue = Column(Float, nullable=False)
    credit_score = Column(Integer, nullable=False)
    years_in_business = Column(Integer, nullable=False)
    existing_loans = Column(Integer, nullable=False)
    past_defaults = Column(Integer, nullable=False)
    gmv = Column(Float, default=0.0, nullable=True)  # Gross Merchandise Value
    refund_rate = Column(Float, default=0.0, nullable=True)  # Refund rate as percentage (0-1)
    chargeback_rate = Column(Float, default=0.0, nullable=True)  # Chargeback rate as percentage (0-1)
