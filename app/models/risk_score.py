from sqlalchemy import Column, Integer, String, ForeignKey, Text
from app.db.base import Base


class RiskScore(Base):
    """
    SQLAlchemy model for risk assessment results.
    
    Stores underwriting decision, risk scoring, and financial offers for a merchant.
    Tracks offer acceptance status for dashboard simulation.
    """
    __tablename__ = "risk_scores"

    id = Column(Integer, primary_key=True, index=True)
    merchant_id = Column(String, ForeignKey("merchants.merchant_id"), nullable=False, index=True)
    risk_score = Column(Integer, nullable=False)
    risk_tier = Column(String, nullable=False)
    decision = Column(String, nullable=False)
    explanation = Column(String, nullable=False)
    financial_offer = Column(Text, nullable=True)  # JSON-serialized FinancialOffer (optional)
    offer_status = Column(String, default="PENDING", nullable=False)  # PENDING | ACCEPTED | REJECTED
    whatsapp_status = Column(String, default="NOT_SENT", nullable=True)  # NOT_SENT | SENT | FAILED
    decision_source = Column(String, default="AGENT", nullable=True)   # AGENT | ADMIN

