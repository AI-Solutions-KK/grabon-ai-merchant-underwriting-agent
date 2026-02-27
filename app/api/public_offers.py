"""
Public offer page routes.

Handles secure token-based access to merchant offers.
No authentication required.
"""

import os
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.merchant import Merchant
from app.models.risk_score import RiskScore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/offer", tags=["public-offers"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/{secure_token}", response_class=HTMLResponse)
def view_merchant_offer(
    secure_token: str,
    request: Request,
    db: Session = Depends(get_db),
    status: str = ""
):
    """
    Public offer view for merchant.
    Accessed via /offer/{secure_token}
    Optional ?status=accepted|rejected query param shows confirmation banner.
    """
    merchant = db.query(Merchant).filter(
        Merchant.secure_token == secure_token
    ).first()

    if not merchant:
        raise HTTPException(status_code=404, detail="Offer not found. Please check the link and try again.")

    risk_score = db.query(RiskScore).filter(
        RiskScore.merchant_id == merchant.merchant_id
    ).order_by(RiskScore.id.desc()).first()

    if not risk_score:
        raise HTTPException(status_code=404, detail="No offer available. Please contact support.")

    financial_offer = {}
    if risk_score.financial_offer:
        try:
            financial_offer = json.loads(risk_score.financial_offer)
        except Exception as e:
            logger.warning(f"Failed to parse financial_offer for {merchant.merchant_id}: {e}")

    return templates.TemplateResponse(
        "public_offer.html",
        {
            "request": request,
            "merchant": merchant,
            "risk_score": {
                "risk_score": risk_score.risk_score,
                "risk_tier": risk_score.risk_tier,
                "decision": risk_score.decision,
                "offer_status": risk_score.offer_status,
                "explanation": risk_score.explanation,
                "financial_offer": risk_score.financial_offer,
            },
            "financial_offer": financial_offer,
            "secure_token": secure_token,
            "status_message": status,   # "accepted" | "rejected" | ""
        }
    )


@router.post("/{secure_token}/accept")
def accept_offer(secure_token: str, db: Session = Depends(get_db)):
    """Record merchant's acceptance of offer and redirect back with status banner."""
    merchant = db.query(Merchant).filter(Merchant.secure_token == secure_token).first()
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")

    risk_score = db.query(RiskScore).filter(
        RiskScore.merchant_id == merchant.merchant_id
    ).order_by(RiskScore.id.desc()).first()

    if risk_score:
        risk_score.offer_status = "ACCEPTED"
        db.commit()
        logger.info(f"[PublicOffer] Offer ACCEPTED by merchant {merchant.merchant_id}")

        # Optional: send confirmation WhatsApp
        _send_confirmation_whatsapp(
            db=db,
            merchant=merchant,
            action="accepted",
            risk_score=risk_score,
        )

    return RedirectResponse(url=f"/offer/{secure_token}?status=accepted", status_code=303)


@router.post("/{secure_token}/reject")
def reject_offer(secure_token: str, db: Session = Depends(get_db)):
    """Record merchant's rejection of offer and redirect back with status banner."""
    merchant = db.query(Merchant).filter(Merchant.secure_token == secure_token).first()
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")

    risk_score = db.query(RiskScore).filter(
        RiskScore.merchant_id == merchant.merchant_id
    ).order_by(RiskScore.id.desc()).first()

    if risk_score:
        risk_score.offer_status = "REJECTED"
        db.commit()
        logger.info(f"[PublicOffer] Offer REJECTED by merchant {merchant.merchant_id}")

    return RedirectResponse(url=f"/offer/{secure_token}?status=rejected", status_code=303)


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _send_confirmation_whatsapp(db, merchant, action: str, risk_score) -> None:
    """
    Send a brief confirmation WhatsApp after merchant accepts (non-blocking).
    Falls back silently on any error.
    """
    try:
        from app.services.whatsapp_service import WhatsAppService
        from app.services.config_service import get_config

        test_override = get_config(db, "test_mobile_override_enabled", "false")
        test_number = get_config(db, "test_mobile_number", "")

        to_number = getattr(merchant, "mobile_number", "") or ""
        if test_override == "true" and test_number:
            to_number = test_number

        if not to_number:
            return

        if not to_number.startswith("whatsapp:"):
            to_number = f"whatsapp:{to_number}"

        msg = (
            f"✅ *Offer Accepted*\n\n"
            f"Thank you, {merchant.merchant_id}!\n"
            f"Your GrabCredit offer has been accepted (Tier: {risk_score.risk_tier}).\n"
            f"Our team will contact you within 24 hours to complete onboarding.\n\n"
            f"_GrabCredit Team_"
        )
        wa = WhatsAppService()
        wa.send_message(to_number, msg)
    except Exception as e:
        logger.warning(f"[PublicOffer] Could not send confirmation WhatsApp: {e}")
