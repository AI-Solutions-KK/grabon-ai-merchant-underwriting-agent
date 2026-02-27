import os
import logging
from typing import Optional
from sqlalchemy.orm import Session
from app.engines.risk_engine import RiskEngine
from app.engines.decision_engine import DecisionEngine
from app.engines.offer_engine import OfferEngine
from app.schemas.merchant_schema import MerchantInput
from app.schemas.decision_schema import UnderwritingDecision
from app.services.merchant_service import MerchantService
from app.services.application_service import RiskScoreService
from app.services.underwriting_agent import ClaudeUnderwritingAgent
from app.services.whatsapp_service import WhatsAppService, normalize_wa_number
from app.services.config_service import get_config
from app.models.risk_score import RiskScore
from app.models.merchant import Merchant as MerchantModel

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    Central orchestrator for merchant underwriting process.
    
    Coordinates:
    - Deterministic risk scoring and decision making
    - AI-powered explanation generation via Claude
    - WhatsApp message delivery of results
    - Data persistence and audit trail
    """
    
    @staticmethod
    def process_underwriting(
        merchant: MerchantInput,
        db: Session,
        whatsapp_number: Optional[str] = None,
        mode: Optional[str] = None
    ) -> UnderwritingDecision:
        """
        Process merchant underwriting request with AI-generated explanations and financial offers.
        
        Flow:
        1. Save merchant via MerchantService
        2. Evaluate risk using RiskEngine.evaluate_risk()
        3. Evaluate decision using DecisionEngine.evaluate()
        4. Calculate financial offer based on mode (credit/insurance)
        5. Generate Claude AI explanation (with fallback)
        6. Construct UnderwritingResult with AI-generated explanation and financial offer
        7. Save risk result via RiskScoreService
        8. Send WhatsApp notification (if number provided, non-blocking)
        9. Return decision
        
        Args:
            merchant: MerchantInput containing merchant financial metrics
            db: SQLAlchemy database session
            whatsapp_number: Optional WhatsApp number to send result (format: whatsapp:+91XXXXXXXXXX)
            mode: Optional mode for financial offer ("credit", "insurance", None for both)
            
        Returns:
            UnderwritingResult: Structured underwriting result with AI explanation and financial offer
        """
        # Step 1: Save merchant to database
        MerchantService.create_merchant(db, merchant)
        
        # Step 2: Evaluate risk with hard rules and weighted scoring
        risk_result = RiskEngine.evaluate_risk(merchant)
        
        # Step 3: Evaluate decision based on risk result
        risk_tier, decision, _ = DecisionEngine.evaluate(risk_result)
        
        # Step 4: Calculate financial offer based on mode
        financial_offer = OfferEngine.calculate_financial_offer(
            risk_tier=risk_tier,
            merchant_data=merchant.dict(),
            mode=mode
        )
        
        # Step 5: Generate Claude AI explanation (with automatic fallback)
        ai_explanation = ClaudeUnderwritingAgent.generate_explanation(
            merchant_data=merchant.dict(),
            risk_score=risk_result["score"],
            risk_tier=risk_tier,
            decision=decision,
            category_benchmark=risk_result.get("category_benchmark", {}),
            gmv_yoy_pct=risk_result.get("gmv_yoy_pct"),
            score_breakdown=risk_result.get("score_breakdown", {}),
        )
        
        # Step 6: Construct UnderwritingResult with AI explanation and financial offer
        underwriting_decision = UnderwritingDecision(
            merchant_id=merchant.merchant_id,
            risk_score=risk_result["score"],
            risk_tier=risk_tier,
            decision=decision,
            explanation=ai_explanation,
            financial_offer=financial_offer
        )
        
        # Step 7: Save risk result to database
        RiskScoreService.create_risk_record(db, underwriting_decision)
        
        # Step 8: Send WhatsApp notification (non-blocking, doesn't affect API response)
        # Skip if underwriting_mode is MANUAL — admin will send manually via dashboard
        # Never send to REJECTED merchants — they have no offer to receive
        underwriting_mode = get_config(db, "underwriting_mode", "AUTO")

        if decision == "REJECTED":
            logger.info(
                f"[WhatsApp] Skipping auto-send for {merchant.merchant_id} — decision is REJECTED (no offer)"
            )
        elif whatsapp_number and underwriting_mode == "AUTO":
            # Respect test-mode override
            test_override_enabled = get_config(db, "test_mobile_override_enabled", "false")
            test_mobile_number = get_config(db, "test_mobile_number", "")
            raw_dest = whatsapp_number
            if test_override_enabled == "true" and test_mobile_number:
                raw_dest = test_mobile_number
                logger.info(f"[TestMode] Overriding WhatsApp number to {raw_dest}")

            send_to = normalize_wa_number(raw_dest)
            if not send_to:
                logger.warning(f"[WhatsApp] Invalid destination '{raw_dest}' for {merchant.merchant_id} — skipping")
            else:
                try:
                    # Fetch saved merchant record to get secure_token for offer link
                    saved_merchant = db.query(MerchantModel).filter_by(
                        merchant_id=merchant.merchant_id
                    ).first()
                    base_url = os.getenv("APP_BASE_URL", "http://localhost:8000")
                    offer_link = (
                        f"{base_url}/offer/{saved_merchant.secure_token}"
                        if saved_merchant and getattr(saved_merchant, "secure_token", None)
                        else ""
                    )

                    # Serialize financial_offer to plain dict for message formatter
                    fo_dict = financial_offer.dict() if financial_offer and hasattr(financial_offer, "dict") else {}

                    whatsapp_service = WhatsAppService()
                    result = whatsapp_service.send_underwriting_result(
                        to_number=send_to,
                        merchant_id=merchant.merchant_id,
                        merchant_name=getattr(merchant, "business_name", "") or merchant.merchant_id,
                        risk_tier=risk_tier,
                        decision=decision,
                        risk_score=risk_result["score"],
                        explanation=ai_explanation,
                        financial_offer=fo_dict,
                        secure_offer_link=offer_link,
                    )
                    # Update whatsapp_status on the saved risk record
                    saved_record = db.query(RiskScore).filter(
                        RiskScore.merchant_id == merchant.merchant_id
                    ).order_by(RiskScore.id.desc()).first()
                    if saved_record:
                        wa_status = result.get("status", "failed")
                        saved_record.whatsapp_status = "SENT" if wa_status in ("queued", "sent", "delivered") else "FAILED"
                        db.commit()
                    logger.info(
                        f"WhatsApp notification sent | Merchant: {merchant.merchant_id} | "
                        f"SID: {result.get('sid')} | Status: {result.get('status')}"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to send WhatsApp notification for {merchant.merchant_id}: {e}",
                        exc_info=True
                    )
        elif underwriting_mode == "MANUAL" and decision != "REJECTED":
            logger.info(f"Underwriting mode is MANUAL — skipping auto WhatsApp for {merchant.merchant_id} (manual send available via dashboard)")
        
        # Step 9: Return decision
        return underwriting_decision
