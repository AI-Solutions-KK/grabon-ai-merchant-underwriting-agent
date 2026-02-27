from sqlalchemy import Column, Integer, String, Float, JSON, CHAR
from app.db.base import Base
from uuid import uuid4


class Merchant(Base):
    """
    SQLAlchemy model for merchant information.
    
    Stores merchant financial metrics and business history.
    Aligns with Project 07 SOW requirements.
    """
    __tablename__ = "merchants"

    # Core identification
    id = Column(Integer, primary_key=True, index=True)
    merchant_id = Column(String, unique=True, index=True, nullable=False)
    secure_token = Column(CHAR(36), unique=True, index=True, nullable=False, default=lambda: str(uuid4()))
    mobile_number = Column(String, nullable=True)  # e.g. +919876543210
    category = Column(String, nullable=True)  # e.g., "Electronics", "Fashion", "Food & Beverage"
    
    # Legacy fields (preserved for backward compatibility)
    monthly_revenue = Column(Float, nullable=False)
    credit_score = Column(Integer, nullable=False)
    years_in_business = Column(Integer, nullable=False)
    existing_loans = Column(Integer, nullable=False)
    past_defaults = Column(Integer, nullable=False)
    gmv = Column(Float, default=0.0, nullable=True)  # Current GMV snapshot
    refund_rate = Column(Float, default=0.0, nullable=True)
    chargeback_rate = Column(Float, default=0.0, nullable=True)
    
    # SOW-required behavioral metrics
    monthly_gmv_12m = Column(JSON, default=[], nullable=True)  # Array of 12 monthly GMV values
    coupon_redemption_rate = Column(Float, default=0.0, nullable=True)  # Rate 0-1
    unique_customer_count = Column(Integer, default=0, nullable=True)  # Total unique customers
    customer_return_rate = Column(Float, default=0.0, nullable=True)  # % of returning customers (0-1)
    avg_order_value = Column(Float, default=0.0, nullable=True)  # Average order value in currency
    seasonality_index = Column(Float, default=1.0, nullable=True)  # Peak/trough ratio
    deal_exclusivity_rate = Column(Float, default=0.0, nullable=True)  # % exclusive deals (0-1)
    return_and_refund_rate = Column(Float, default=0.0, nullable=True)  # % returns/refunds (0-1)
