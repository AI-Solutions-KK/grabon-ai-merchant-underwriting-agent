"""
Batch Underwriting Engine Service

Processes up to 10 merchants in a single engine run.
Called by POST /admin/run-engine (button-triggered, not scheduled).
"""

import logging
import json
from typing import Dict
from sqlalchemy.orm import Session

from app.models.merchant import Merchant
from app.models.risk_score import RiskScore
from app.schemas.merchant_schema import MerchantInput
from app.orchestrator.orchestrator import Orchestrator
from app.services.config_service import get_config, set_config
from app.services.whatsapp_service import normalize_wa_number

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
        auto_mode = get_config(db, "underwriting_mode", "AUTO") == "AUTO"
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
                # Build MerchantInput from stored merchant row
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

                # Determine WhatsApp number (AUTO mode)
                # Priority: test_override number > merchant's own number
                wa_number = None
                if auto_mode:
                    test_override = get_config(db, "test_mobile_override_enabled", "false")
                    test_num = get_config(db, "test_mobile_number", "")
                    if test_override == "true" and test_num:
                        # Test mode: route ALL auto-sends to the override number
                        wa_number = normalize_wa_number(test_num)
                        logger.info(f"[Engine] TestMode override → sending WA for {merchant.merchant_id} to {test_num}")
                    elif merchant.mobile_number:
                        wa_number = normalize_wa_number(merchant.mobile_number)
                        if not wa_number:
                            logger.warning(f"[Engine] Invalid mobile '{merchant.mobile_number}' for {merchant.merchant_id} — skipping WA")

                # Run underwriting (orchestrator handles WA send internally in AUTO)
                decision = Orchestrator.process_underwriting(
                    merchant=merchant_input,
                    db=db,
                    whatsapp_number=wa_number,
                    mode=None,
                )

                stats["processed"] += 1
                row_detail["decision"] = decision.decision
                row_detail["tier"] = decision.risk_tier

                if "APPROVED" in decision.decision:
                    stats["approved"] += 1
                else:
                    stats["rejected"] += 1

                # Read WA status that orchestrator wrote
                saved_rs = db.query(RiskScore).filter(
                    RiskScore.merchant_id == merchant.merchant_id
                ).order_by(RiskScore.id.desc()).first()

                if saved_rs:
                    wa_st = getattr(saved_rs, "whatsapp_status", "NOT_SENT")
                    row_detail["wa_status"] = wa_st
                    if wa_st == "SENT":
                        stats["wa_sent"] += 1
                    elif wa_st == "FAILED":
                        stats["wa_failed"] += 1
                    else:
                        stats["wa_skipped"] += 1
                else:
                    stats["wa_skipped"] += 1

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
