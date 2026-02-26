"""
Dashboard routes for merchant underwriting UI

Provides:
- Merchant list view
- Merchant detail view
- Accept offer simulation
"""

import logging
from fastapi import APIRouter, Depends, Request, HTTPException, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.merchant import Merchant
from app.models.risk_score import RiskScore

logger = logging.getLogger(__name__)

# Initialize templates
templates = Jinja2Templates(directory="app/templates")

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/")
def dashboard_home(request: Request, db: Session = Depends(get_db)):
    """
    Dashboard home page with merchant list
    """
    merchants = db.query(Merchant).all()
    
    # Enrich with latest risk scores
    merchants_data = []
    for merchant in merchants:
        risk_score = db.query(RiskScore).filter(
            RiskScore.merchant_id == merchant.merchant_id
        ).order_by(RiskScore.id.desc()).first()
        
        merchants_data.append({
            "merchant": merchant,
            "risk_score": risk_score
        })
    
    return templates.TemplateResponse(
        "merchant_list.html",
        {
            "request": request,
            "merchants_data": merchants_data,
            "page_title": "Merchant Dashboard"
        }
    )


@router.get("/{merchant_id}")
def merchant_detail(merchant_id: str, request: Request, db: Session = Depends(get_db)):
    """
    Merchant detail page with full underwriting info
    """
    merchant = db.query(Merchant).filter(
        Merchant.merchant_id == merchant_id
    ).first()
    
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")
    
    risk_score = db.query(RiskScore).filter(
        RiskScore.merchant_id == merchant_id
    ).order_by(RiskScore.id.desc()).first()
    
    if not risk_score:
        raise HTTPException(status_code=404, detail="No underwriting record found")
    
    return templates.TemplateResponse(
        "merchant_detail.html",
        {
            "request": request,
            "merchant": merchant,
            "risk_score": risk_score,
            "page_title": f"Merchant {merchant_id} - Details"
        }
    )


@router.post("/{merchant_id}/accept")
def accept_offer(merchant_id: str, db: Session = Depends(get_db)):
    """
    Accept offer for merchant (simulation)
    Updates offer_status to ACCEPTED and redirects back to detail page
    """
    risk_score = db.query(RiskScore).filter(
        RiskScore.merchant_id == merchant_id
    ).order_by(RiskScore.id.desc()).first()
    
    if not risk_score:
        raise HTTPException(status_code=404, detail="Underwriting record not found")
    
    # Mark offer as accepted
    risk_score.offer_status = "ACCEPTED"
    db.commit()
    
    logger.info(f"Offer accepted for merchant {merchant_id}")
    
    # Redirect back to detail page with success indicator
    return RedirectResponse(url=f"/dashboard/{merchant_id}", status_code=303)
