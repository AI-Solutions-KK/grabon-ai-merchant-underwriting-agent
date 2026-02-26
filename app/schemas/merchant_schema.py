from pydantic import BaseModel, Field


class MerchantInput(BaseModel):
    """
    Pydantic model for merchant underwriting input data.
    
    Captures merchant financial metrics and business history for risk assessment.
    """
    merchant_id: str = Field(..., description="Unique identifier for the merchant")
    monthly_revenue: float = Field(..., gt=0, description="Monthly revenue in currency units")
    credit_score: int = Field(..., ge=300, le=850, description="Credit score (300-850)")
    years_in_business: int = Field(..., ge=0, description="Number of years the business has been operating")
    existing_loans: int = Field(..., ge=0, description="Number of existing loans")
    past_defaults: int = Field(..., ge=0, description="Number of past defaults")

    class Config:
        json_schema_extra = {
            "example": {
                "merchant_id": "MERCH_12345",
                "monthly_revenue": 50000.0,
                "credit_score": 750,
                "years_in_business": 5,
                "existing_loans": 2,
                "past_defaults": 0
            }
        }
