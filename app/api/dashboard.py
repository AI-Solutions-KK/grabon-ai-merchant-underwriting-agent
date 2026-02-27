"""
Dashboard routes for merchant underwriting UI

Provides:
- Merchant list view
- Merchant detail view
- Accept offer simulation
"""

import logging
import os
import json
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, Depends, Request, HTTPException, Form
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from fastapi.responses import RedirectResponse, JSONResponse
from app.db.session import get_db
from app.models.merchant import Merchant
from app.models.risk_score import RiskScore
from app.schemas.decision_schema import FinancialOffer
from app.services.config_service import get_config, set_config
from app.services.whatsapp_service import normalize_wa_number

logger = logging.getLogger(__name__)

# Initialize templates with absolute path
templates_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "app", "templates")
templates = Jinja2Templates(directory=templates_dir)

# Add custom Jinja2 global function for now
templates.env.globals.update(now=datetime.now)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/")
def dashboard_home(request: Request, db: Session = Depends(get_db)):
    """Dashboard home — merchant list with engine trigger button."""
    merchants = db.query(Merchant).all()

    merchants_data = []
    for merchant in merchants:
        risk_score = db.query(RiskScore).filter(
            RiskScore.merchant_id == merchant.merchant_id
        ).order_by(RiskScore.id.desc()).first()
        merchants_data.append({"merchant": merchant, "risk_score": risk_score})

    # Engine summary (stored after last engine run)
    engine_summary = None
    ep = request.query_params.get("engine", "")
    if ep in ("done", "always_on"):
        raw = get_config(db, "last_engine_summary", "")
        if raw:
            try:
                engine_summary = json.loads(raw)
            except Exception:
                engine_summary = None

    underwriting_mode = get_config(db, "underwriting_mode", "AUTO")
    test_override_enabled = get_config(db, "test_mobile_override_enabled", "false")
    test_mobile_number = get_config(db, "test_mobile_number", "")
    engine_state = get_config(db, "engine_state", "OFF")

    from app.services import monitor_service as _ms
    monitor_running = _ms.is_running()

    return templates.TemplateResponse(
        "merchant_list.html",
        {
            "request": request,
            "merchants_data": merchants_data,
            "page_title": "Merchant Dashboard",
            "engine_summary": engine_summary,
            "underwriting_mode": underwriting_mode,
            "test_override_enabled": test_override_enabled,
            "test_mobile_number": test_mobile_number,
            "engine_state": engine_state,
            "monitor_running": monitor_running,
        }
    )


@router.get("/{merchant_id}")
def merchant_detail(merchant_id: str, request: Request, db: Session = Depends(get_db)):
    """
    Merchant detail page with full underwriting info and financial offers
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
    
    # Deserialize financial_offer from JSON if present
    risk_score_dict = {
        "id": risk_score.id,
        "merchant_id": risk_score.merchant_id,
        "risk_score": risk_score.risk_score,
        "risk_tier": risk_score.risk_tier,
        "decision": risk_score.decision,
        "explanation": risk_score.explanation,
        "offer_status": risk_score.offer_status,
        "whatsapp_status": getattr(risk_score, "whatsapp_status", "NOT_SENT"),
        "decision_source": getattr(risk_score, "decision_source", "AGENT"),
        "financial_offer": None
    }
    
    if risk_score.financial_offer:
        try:
            offer_data = json.loads(risk_score.financial_offer)
            risk_score_dict["financial_offer"] = offer_data
        except json.JSONDecodeError:
            logger.warning(f"Failed to deserialize financial_offer for merchant {merchant_id}")
            risk_score_dict["financial_offer"] = None

    # All merchants for dropdown selector
    all_merchants = db.query(Merchant).all()

    # System config for test-mode panel and underwriting mode
    test_override_enabled = get_config(db, "test_mobile_override_enabled", "false")
    test_mobile_number = get_config(db, "test_mobile_number", "")
    underwriting_mode = get_config(db, "underwriting_mode", "AUTO")

    return templates.TemplateResponse(
        "merchant_detail.html",
        {
            "request": request,
            "merchant": merchant,
            "risk_score": risk_score_dict,
            "page_title": f"Merchant {merchant_id} - Details",
            "all_merchants": all_merchants,
            "success_message": request.query_params.get("success"),
            "test_override_enabled": test_override_enabled,
            "test_mobile_number": test_mobile_number,
            "underwriting_mode": underwriting_mode,
        }
    )


@router.post("/config/test-mode")
def save_test_mode_config(
    test_override_enabled: str = Form("false"),
    test_mobile_number: str = Form(""),
    db: Session = Depends(get_db)
):
    """Save WhatsApp test-mode override settings."""
    set_config(db, "test_mobile_override_enabled", test_override_enabled)
    set_config(db, "test_mobile_number", test_mobile_number.strip())
    logger.info(f"Test mode override set: enabled={test_override_enabled}, number={test_mobile_number.strip()}")
    return RedirectResponse(url="/dashboard/?success=Test+mode+settings+saved", status_code=303)


@router.post("/config/underwriting-mode")
def save_underwriting_mode(
    underwriting_mode: str = Form("AUTO"),
    db: Session = Depends(get_db)
):
    """Save underwriting auto/manual mode."""
    mode = underwriting_mode.upper()
    if mode not in ("AUTO", "MANUAL"):
        mode = "AUTO"
    set_config(db, "underwriting_mode", mode)
    logger.info(f"Underwriting mode set to: {mode}")
    return RedirectResponse(url="/dashboard/?success=Underwriting+mode+updated", status_code=303)


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

    risk_score.offer_status = "ACCEPTED"
    db.commit()
    logger.info(f"Offer accepted for merchant {merchant_id}")

    # Send confirmation WhatsApp (non-blocking, fail-safe)
    _send_acceptance_confirmation(db, merchant_id, risk_score)

    return RedirectResponse(
        url=f"/dashboard/{merchant_id}?success=Offer+accepted+and+confirmation+sent",
        status_code=303
    )


def _send_acceptance_confirmation(db, merchant_id: str, risk_score) -> None:
    """Send a brief acceptance confirmation via WhatsApp. Silently skips on any error."""
    try:
        from app.services.whatsapp_service import WhatsAppService

        merchant = db.query(Merchant).filter(Merchant.merchant_id == merchant_id).first()
        if not merchant:
            return

        # Respect test-mode override
        test_override = get_config(db, "test_mobile_override_enabled", "false")
        test_number = get_config(db, "test_mobile_number", "")
        raw_number = merchant.mobile_number or ""
        if test_override == "true" and test_number:
            raw_number = test_number

        if not raw_number.strip():
            logger.info(f"[Accept] No mobile for {merchant_id} — skipping confirmation WA")
            return

        to_number = normalize_wa_number(raw_number)
        if not to_number:
            logger.warning(f"[Accept] Invalid mobile '{raw_number}' for {merchant_id} — skipping WA")
            return

        msg = (
            f"✅ *Offer Confirmation*\n\n"
            f"Dear {merchant_id},\n\n"
            f"Your GrabCredit offer has been successfully accepted.\n"
            f"Risk Tier: {risk_score.risk_tier}\n\n"
            f"Our onboarding team will contact you shortly.\n\n"
            f"— GrabCredit Team"
        )
        wa = WhatsAppService()
        wa.send_message(to_number, msg)
        logger.info(f"[Accept] Confirmation WA sent to {to_number}")
    except Exception as e:
        logger.warning(f"[Accept] Confirmation WA failed for {merchant_id}: {e}")


@router.post("/{merchant_id}/update-mobile")
def update_mobile(merchant_id: str, mobile_number: str = Form(...), db: Session = Depends(get_db)):
    """Update mobile from detail page (redirect response)."""
    merchant = db.query(Merchant).filter(Merchant.merchant_id == merchant_id).first()
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")
    merchant.mobile_number = mobile_number.strip()
    db.commit()
    logger.info(f"Mobile updated for merchant {merchant_id}: {mobile_number}")
    return RedirectResponse(
        url=f"/dashboard/{merchant_id}?success=Mobile+number+updated+successfully",
        status_code=303
    )


@router.post("/{merchant_id}/mobile-inline")
def update_mobile_inline(merchant_id: str, request: Request, mobile_number: str = Form(...), db: Session = Depends(get_db)):
    """
    AJAX endpoint — update mobile number from main table inline editor.
    After saving:
      1. Wipes the stored fingerprint so the next engine cycle re-processes this merchant.
      2. If the merchant already has an APPROVED decision, sends WA immediately to the new number.
    Returns JSON {ok, number, wa_sent, wa_status} for the JS to show live feedback.
    """
    merchant = db.query(Merchant).filter(Merchant.merchant_id == merchant_id).first()
    if not merchant:
        return JSONResponse({"ok": False, "error": "Merchant not found"}, status_code=404)

    raw = mobile_number.strip()
    if not raw:
        return JSONResponse({"ok": False, "error": "Number cannot be empty"}, status_code=400)

    merchant.mobile_number = raw
    db.commit()
    logger.info(f"[Inline] Mobile updated for {merchant_id}: {raw}")

    # Wipe stored fingerprint so engine re-processes this merchant on next cycle
    from app.services.config_service import set_config as _set_config
    _set_config(db, f"fp_{merchant_id}", "")  # empty = will be treated as changed
    logger.info(f"[Inline] Fingerprint wiped for {merchant_id} — engine will re-detect")

    # If merchant already has an approved decision, send WA immediately to the new number
    wa_sent = False
    wa_status = "not_sent"
    wa_error = None

    risk_score = db.query(RiskScore).filter(
        RiskScore.merchant_id == merchant_id
    ).order_by(RiskScore.id.desc()).first()

    if risk_score and risk_score.decision not in ("REJECTED", None, ""):
        try:
            from app.services.whatsapp_service import WhatsAppService, normalize_wa_number
            test_override = get_config(db, "test_mobile_override_enabled", "false")
            test_num = get_config(db, "test_mobile_number", "")
            dest = test_num if test_override == "true" and test_num else raw
            to_number = normalize_wa_number(dest)

            if to_number:
                fo_dict = {}
                if risk_score.financial_offer:
                    try:
                        import json as _json
                        fo_dict = _json.loads(risk_score.financial_offer)
                    except Exception:
                        fo_dict = {}

                base_url = os.getenv("APP_BASE_URL", "http://localhost:8000")
                offer_link = (
                    f"{base_url}/offer/{merchant.secure_token}"
                    if getattr(merchant, "secure_token", None) else ""
                )
                result = WhatsAppService().send_underwriting_result(
                    to_number=to_number,
                    merchant_id=merchant_id,
                    merchant_name=getattr(merchant, "business_name", "") or merchant_id,
                    risk_tier=risk_score.risk_tier,
                    decision=risk_score.decision,
                    risk_score=risk_score.risk_score,
                    explanation=risk_score.explanation or "",
                    financial_offer=fo_dict,
                    secure_offer_link=offer_link,
                )
                wa_sent = (
                    result.get("status") in ("queued", "sent", "delivered", "accepted")
                    or (bool(result.get("sid")) and result.get("sid") not in ("N/A", "", None))
                )
                wa_status = "sent" if wa_sent else "failed"
                if wa_sent:
                    risk_score.whatsapp_status = "SENT"
                    db.commit()
                    logger.info(f"[Inline] ✅ WA sent to {merchant_id} at new number {to_number}")
                else:
                    wa_error = result.get("error", "Unknown error")
                    logger.warning(f"[Inline] ❌ WA failed for {merchant_id}: {wa_error}")
            else:
                wa_status = "bad_number"
                wa_error = f"Cannot normalize: {raw}"
        except Exception as e:
            wa_status = "error"
            wa_error = str(e)
            logger.error(f"[Inline] WA send error for {merchant_id}: {e}", exc_info=True)
    else:
        wa_status = "no_decision_yet" if not risk_score else "rejected"

    return JSONResponse({
        "ok": True,
        "merchant_id": merchant_id,
        "number": raw,
        "wa_sent": wa_sent,
        "wa_status": wa_status,
        "wa_error": wa_error,
    })


@router.post("/{merchant_id}/send-offer")
def send_offer_whatsapp(merchant_id: str, db: Session = Depends(get_db)):
    """
    Manually send the underwriting offer to the merchant via WhatsApp.
    Respects test-mode override. Updates whatsapp_status on RiskScore.
    """
    from app.services.whatsapp_service import WhatsAppService

    merchant = db.query(Merchant).filter(Merchant.merchant_id == merchant_id).first()
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")

    risk_score = db.query(RiskScore).filter(
        RiskScore.merchant_id == merchant_id
    ).order_by(RiskScore.id.desc()).first()
    if not risk_score:
        raise HTTPException(status_code=404, detail="No underwriting record found")

    # Block send for rejected merchants — they have no pre-approved offer
    if risk_score.decision == "REJECTED":
        logger.info(f"[ManualWA] Blocked send for {merchant_id} — decision is REJECTED")
        return RedirectResponse(
            url=f"/dashboard/{merchant_id}?success=Cannot+send+offer+to+REJECTED+merchant",
            status_code=303
        )

    # Determine destination number
    test_override_enabled = get_config(db, "test_mobile_override_enabled", "false")
    test_mobile_number = get_config(db, "test_mobile_number", "")

    raw_number = merchant.mobile_number or ""
    if test_override_enabled == "true" and test_mobile_number:
        raw_number = test_mobile_number
        logger.info(f"[TestMode] Overriding send number to {raw_number} for merchant {merchant_id}")

    if not raw_number:
        logger.warning(f"No mobile number set for merchant {merchant_id} — cannot send WhatsApp")
        return RedirectResponse(
            url=f"/dashboard/{merchant_id}?success=No+mobile+number+set+for+this+merchant",
            status_code=303
        )

    # Normalize to whatsapp:+E.164
    to_number = normalize_wa_number(raw_number)
    if not to_number:
        return RedirectResponse(
            url=f"/dashboard/{merchant_id}?success=Invalid+phone+number+format",
            status_code=303
        )

    # Build secure offer link for message
    base_url = os.getenv("APP_BASE_URL", "http://localhost:8000")
    offer_link = (
        f"{base_url}/offer/{merchant.secure_token}"
        if getattr(merchant, "secure_token", None)
        else ""
    )

    # Parse financial_offer to dict for message formatter
    fo_dict = {}
    if risk_score.financial_offer:
        try:
            fo_dict = json.loads(risk_score.financial_offer)
        except Exception:
            fo_dict = {}

    wa_service = WhatsAppService()
    result = wa_service.send_underwriting_result(
        to_number=to_number,
        merchant_id=merchant_id,
        merchant_name=getattr(merchant, "business_name", "") or merchant_id,
        risk_tier=risk_score.risk_tier,
        decision=risk_score.decision,
        risk_score=risk_score.risk_score,
        explanation=risk_score.explanation or "",
        financial_offer=fo_dict,
        secure_offer_link=offer_link,
    )

    # Update whatsapp_status
    if result.get("status") in ("queued", "sent", "delivered"):
        risk_score.whatsapp_status = "SENT"
        status_msg = "WhatsApp+offer+sent+successfully"
    else:
        risk_score.whatsapp_status = "FAILED"
        status_msg = "WhatsApp+send+failed+check+logs"

    db.commit()
    logger.info(f"WhatsApp send for merchant {merchant_id}: {result}")

    return RedirectResponse(
        url=f"/dashboard/{merchant_id}?success={status_msg}",
        status_code=303
    )
