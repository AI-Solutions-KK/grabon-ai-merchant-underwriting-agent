"""
Batch Underwriting Engine Service

Processes up to 10 merchants in a single engine run.
Called by POST /admin/run-engine (button-triggered, not scheduled).

WA sending logic:
  - Engine run = explicit admin action → ALWAYS sends to approved merchants
    regardless of AUTO/MANUAL mode setting.
  - AUTO/MANUAL mode only governs API-triggered (per-merchant) flows.
  - REJECTED merchants never receive a WhatsApp message.
  - Test-override routes all sends to the override number when enabled.
"""

import json
import logging
import os
from typing import Dict

from sqlalchemy.orm import Session

from app.models.merchant import Merchant
from app.models.risk_score import RiskScore
from app.orchestrator.orchestrator import Orchestrator
from app.schemas.merchant_schema import MerchantInput
from app.services.config_service import get_config, set_config
from app.services.whatsapp_service import WhatsAppService, normalize_wa_number

logger = logging.getLogger(__name__)


class EngineService:
    """
    Batch underwriting engine.

    For each stored merchant (limit 10):
    - Builds MerchantInput from DB row
    - Calls Orchestrator.process_underwriting()
    - Sends WhatsApp if AUTO mode is ON and mobile number is present

    Never raises — failures are logged and the engine continues.
    """

    @staticmethod
    def run_all_merchants(db: Session) -> Dict:
        """
        Run underwriting for all merchants (max 10).

        Returns:
            {
              "processed": int,
              "approved": int,
              "rejected": int,
              "wa_sent": int,
              "wa_failed": int,
              "wa_skipped": int,
              "errors": int,
              "details": [{"merchant_id", "decision", "tier", "wa_status"}, ...]
            }
        """
        merchants = db.query(Merchant).limit(10).all()

        stats = {
            "processed": 0,
            "approved": 0,
            "rejected": 0,
            "wa_sent": 0,
            "wa_failed": 0,
            "wa_skipped": 0,
            "errors": 0,
            "details": [],
        }

        for merchant in merchants:
            row_detail = {
                "merchant_id": merchant.merchant_id,
                "decision": "ERROR",
                "tier": "—",
                "wa_status": "SKIPPED",
            }

            try:
                # Build MerchantInput fresh from current DB row — always uses latest data
                merchant_input = MerchantInput(
                    merchant_id=merchant.merchant_id,
                    category=merchant.category or "General",
                    monthly_revenue=merchant.monthly_revenue,
                    credit_score=merchant.credit_score,
                    years_in_business=merchant.years_in_business,
                    existing_loans=merchant.existing_loans or 0,
                    past_defaults=merchant.past_defaults or 0,
                    gmv=merchant.gmv or 0.0,
                    refund_rate=merchant.refund_rate or 0.0,
                    chargeback_rate=merchant.chargeback_rate or 0.0,
                    coupon_redemption_rate=merchant.coupon_redemption_rate or 0.0,
                    unique_customer_count=merchant.unique_customer_count or 0,
                    customer_return_rate=merchant.customer_return_rate or 0.0,
                    avg_order_value=merchant.avg_order_value or 0.0,
                    seasonality_index=merchant.seasonality_index or 1.0,
                    deal_exclusivity_rate=merchant.deal_exclusivity_rate or 0.0,
                    return_and_refund_rate=merchant.return_and_refund_rate or 0.0,
                )

                # Pass whatsapp_number=None — engine handles WA itself below,
                # so orchestrator's AUTO/MANUAL gate never blocks us.
                decision = Orchestrator.process_underwriting(
                    merchant=merchant_input,
                    db=db,
                    whatsapp_number=None,
                    mode=None,
                )

                stats["processed"] += 1
                row_detail["decision"] = decision.decision
                row_detail["tier"] = decision.risk_tier

                if "APPROVED" in decision.decision:
                    stats["approved"] += 1
                else:
                    stats["rejected"] += 1

                # ── Engine WA send: always fires for non-rejected, ignores AUTO/MANUAL ──
                # Reads fresh config each iteration so changes take effect immediately.
                saved_rs = db.query(RiskScore).filter(
                    RiskScore.merchant_id == merchant.merchant_id
                ).order_by(RiskScore.id.desc()).first()

                if decision.decision != "REJECTED":
                    # Resolve destination number (test-override takes priority)
                    test_override = get_config(db, "test_mobile_override_enabled", "false")
                    test_num = get_config(db, "test_mobile_number", "")

                    if test_override == "true" and test_num:
                        raw_dest = test_num
                        logger.info(f"[Engine] TestMode → routing {merchant.merchant_id} WA to {raw_dest}")
                    else:
                        raw_dest = merchant.mobile_number or ""

                    to_number = normalize_wa_number(raw_dest) if raw_dest else ""

                    if not to_number:
                        logger.info(
                            f"[Engine] No valid mobile for {merchant.merchant_id} "
                            f"(mobile={merchant.mobile_number!r}) — skipping WA"
                        )
                        row_detail["wa_status"] = "SKIPPED"
                        stats["wa_skipped"] += 1
                    else:
                        try:
                            # Build offer link from saved merchant's secure_token
                            base_url = os.getenv("APP_BASE_URL", "http://localhost:8000")
                            offer_link = (
                                f"{base_url}/offer/{merchant.secure_token}"
                                if getattr(merchant, "secure_token", None)
                                else ""
                            )
                            # Serialize financial offer for message formatter
                            import json as _json
                            fo_dict = {}
                            if saved_rs and saved_rs.financial_offer:
                                try:
                                    fo_dict = _json.loads(saved_rs.financial_offer)
                                except Exception:
                                    fo_dict = {}

                            wa_svc = WhatsAppService()
                            result = wa_svc.send_underwriting_result(
                                to_number=to_number,
                                merchant_id=merchant.merchant_id,
                                merchant_name=getattr(merchant, "business_name", "") or merchant.merchant_id,
                                risk_tier=decision.risk_tier,
                                decision=decision.decision,
                                risk_score=saved_rs.risk_score if saved_rs else 0,
                                explanation=saved_rs.explanation or "" if saved_rs else "",
                                financial_offer=fo_dict,
                                secure_offer_link=offer_link,
                            )

                            wa_status_val = result.get("status", "failed")
                            is_sent = wa_status_val in ("queued", "sent", "delivered")

                            if saved_rs:
                                saved_rs.whatsapp_status = "SENT" if is_sent else "FAILED"
                                db.commit()

                            row_detail["wa_status"] = "SENT" if is_sent else "FAILED"
                            if is_sent:
                                stats["wa_sent"] += 1
                                logger.info(f"[Engine] WA sent → {merchant.merchant_id} | to={to_number} | sid={result.get('sid')}")
                            else:
                                stats["wa_failed"] += 1
                                logger.warning(f"[Engine] WA failed → {merchant.merchant_id} | {result.get('error')}")

                        except Exception as wa_err:
                            stats["wa_failed"] += 1
                            row_detail["wa_status"] = "FAILED"
                            logger.error(f"[Engine] WA exception for {merchant.merchant_id}: {wa_err}", exc_info=True)
                else:
                    # REJECTED — never send
                    row_detail["wa_status"] = "NOT_SENT"
                    stats["wa_skipped"] += 1
                    logger.info(f"[Engine] Skipping WA for {merchant.merchant_id} — REJECTED")

            except Exception as e:
                stats["errors"] += 1
                logger.error(f"[Engine] Failed to process {merchant.merchant_id}: {e}", exc_info=True)
                row_detail["wa_status"] = "ERROR"

            stats["details"].append(row_detail)

        # Persist summary for dashboard display
        set_config(db, "last_engine_summary", json.dumps(stats))

        logger.info(
            f"[Engine] Run complete | "
            f"Processed: {stats['processed']} | "
            f"Approved: {stats['approved']} | "
            f"Rejected: {stats['rejected']} | "
            f"WA Sent: {stats['wa_sent']} | "
            f"WA Failed: {stats['wa_failed']}"
        )
        return stats
