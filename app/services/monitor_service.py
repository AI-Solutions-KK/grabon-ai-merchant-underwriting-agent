"""
Background Merchant Monitor
============================
Runs in a daemon thread when engine_state == "ALWAYS_ON".

Logic per cycle (every POLL_INTERVAL seconds):
  For each merchant:
    1. Compute a fingerprint of their scoring-relevant data fields.
    2. Compare with the last stored fingerprint.
    3. If fingerprint changed OR no risk record exists → re-run underwriting.
    4. After assessment:
         - APPROVED / APPROVED_WITH_CONDITIONS + has valid mobile → send WA
         - REJECTED → never send WA
         - WA already SENT for *this fingerprint* → skip (no duplicate)

Engine states (stored in config table as "engine_state"):
    OFF        — monitor thread not running, engine inactive
    ON         — run one batch immediately, then set state back to OFF
    ALWAYS_ON  — run continuously every POLL_INTERVAL seconds
"""

import hashlib
import json
import logging
import os
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)

POLL_INTERVAL = int(os.getenv("MONITOR_POLL_INTERVAL", "60"))   # seconds between cycles

# Singleton thread handle
_monitor_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()


# ── Fingerprint helpers ────────────────────────────────────────────────────────

def _merchant_fingerprint(merchant) -> str:
    """
    Return an MD5 hex digest of the merchant's scoring-relevant fields.
    Includes mobile_number so a phone-number change also triggers re-assessment.
    If ANY of these values change the fingerprint changes → triggers re-assessment + WA.
    """
    payload = {
        "credit_score": merchant.credit_score,
        "monthly_revenue": merchant.monthly_revenue,
        "years_in_business": merchant.years_in_business,
        "existing_loans": merchant.existing_loans or 0,
        "past_defaults": merchant.past_defaults or 0,
        "refund_rate": round(merchant.refund_rate or 0.0, 4),
        "chargeback_rate": round(merchant.chargeback_rate or 0.0, 4),
        "customer_return_rate": round(merchant.customer_return_rate or 0.0, 4),
        "deal_exclusivity_rate": round(merchant.deal_exclusivity_rate or 0.0, 4),
        "return_and_refund_rate": round(merchant.return_and_refund_rate or 0.0, 4),
        "seasonality_index": round(merchant.seasonality_index or 1.0, 4),
        "category": merchant.category or "",
        # Include mobile so a number change forces re-assessment and re-send
        "mobile_number": (merchant.mobile_number or "").strip(),
    }
    raw = json.dumps(payload, sort_keys=True)
    return hashlib.md5(raw.encode()).hexdigest()


# ── Core cycle ─────────────────────────────────────────────────────────────────

def _run_cycle(db_session_factory) -> dict:
    """
    Process all merchants in a single monitor cycle.
    Opens its own DB session — safe to call from a background thread OR synchronously.
    Returns a stats dict: {processed, approved, rejected, wa_sent, wa_failed, wa_skipped}
    """
    from app.models.merchant import Merchant
    from app.models.risk_score import RiskScore
    from app.schemas.merchant_schema import MerchantInput
    from app.orchestrator.orchestrator import Orchestrator
    from app.services.config_service import get_config, set_config
    from app.services.whatsapp_service import WhatsAppService, normalize_wa_number

    stats = {"processed": 0, "approved": 0, "rejected": 0, "wa_sent": 0, "wa_failed": 0, "wa_skipped": 0}

    db = db_session_factory()
    try:
        merchants = db.query(Merchant).all()
        logger.info(f"[Monitor] Cycle started — checking {len(merchants)} merchants")

        for merchant in merchants:
            try:
                fingerprint = _merchant_fingerprint(merchant)
                fp_key = f"fp_{merchant.merchant_id}"
                stored_fp = get_config(db, fp_key, "")

                # Latest risk record
                rs = db.query(RiskScore).filter_by(
                    merchant_id=merchant.merchant_id
                ).order_by(RiskScore.id.desc()).first()

                data_changed = fingerprint != stored_fp
                no_record = rs is None

                if not data_changed and not no_record:
                    logger.debug(f"[Monitor] {merchant.merchant_id} — unchanged, skipping")
                    continue

                reason = "no_record" if no_record else "data_changed"
                logger.info(f"[Monitor] {merchant.merchant_id} — re-assessing ({reason})")
                stats["processed"] += 1

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

                # Run underwriting (no WA from orchestrator — we handle it below)
                decision = Orchestrator.process_underwriting(
                    merchant=merchant_input,
                    db=db,
                    whatsapp_number=None,
                    mode=None,
                )

                # Store new fingerprint so we don't re-process unchanged data
                set_config(db, fp_key, fingerprint)

                if decision.decision == "REJECTED":
                    logger.info(f"[Monitor] {merchant.merchant_id} → REJECTED — no WA sent")
                    stats["rejected"] += 1
                    continue
                stats["approved"] += 1

                # ── Send WA ───────────────────────────────────────────────────
                test_override = get_config(db, "test_mobile_override_enabled", "false")
                test_num = get_config(db, "test_mobile_number", "")
                raw_dest = (
                    test_num if test_override == "true" and test_num
                    else (merchant.mobile_number or "")
                )

                to_number = normalize_wa_number(raw_dest) if raw_dest else ""
                if not to_number:
                    logger.info(f"[Monitor] {merchant.merchant_id} → no valid mobile, skip WA")
                    stats["wa_skipped"] += 1
                    continue

                # Fetch latest risk record (just saved by orchestrator)
                saved_rs = db.query(RiskScore).filter_by(
                    merchant_id=merchant.merchant_id
                ).order_by(RiskScore.id.desc()).first()

                fo_dict = {}
                if saved_rs and saved_rs.financial_offer:
                    try:
                        fo_dict = json.loads(saved_rs.financial_offer)
                    except Exception:
                        fo_dict = {}

                base_url = os.getenv("APP_BASE_URL", "http://localhost:8000")
                offer_link = (
                    f"{base_url}/offer/{merchant.secure_token}"
                    if getattr(merchant, "secure_token", None) else ""
                )

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

                wa_ok = result.get("status") in ("queued", "sent", "delivered")
                if saved_rs:
                    saved_rs.whatsapp_status = "SENT" if wa_ok else "FAILED"
                    db.commit()

                if wa_ok:
                    logger.info(f"[Monitor] ✅ WA sent → {merchant.merchant_id} | {to_number} | sid={result.get('sid')}")
                    stats["wa_sent"] += 1
                else:
                    logger.warning(f"[Monitor] ❌ WA failed → {merchant.merchant_id} | {result.get('error')}")
                    stats["wa_failed"] += 1

            except Exception as e:
                logger.error(f"[Monitor] Error processing {merchant.merchant_id}: {e}", exc_info=True)
                try:
                    db.rollback()
                except Exception:
                    pass

    finally:
        db.close()

    logger.info(f"[Monitor] Cycle done — {stats}")
    return stats


# ── Thread entry point ─────────────────────────────────────────────────────────

def _monitor_loop(db_session_factory):
    """Background thread: run cycle immediately, then repeat every POLL_INTERVAL."""
    from app.db.session import SessionLocal as _SessionLocal
    from app.services.config_service import get_config, set_config

    logger.info(f"[Monitor] Thread started — poll interval {POLL_INTERVAL}s")

    while not _stop_event.is_set():
        # Re-check state at start of each cycle
        db = db_session_factory()
        try:
            state = get_config(db, "engine_state", "OFF")
        finally:
            db.close()

        if state == "OFF":
            logger.info("[Monitor] engine_state=OFF — thread exiting")
            break

        _run_cycle(db_session_factory)

        if state == "ON":
            # ONE-SHOT: mark OFF after single run
            db = db_session_factory()
            try:
                set_config(db, "engine_state", "OFF")
            finally:
                db.close()
            logger.info("[Monitor] engine_state=ON → single run done, state set to OFF")
            break

        # ALWAYS_ON: wait, then loop
        _stop_event.wait(timeout=POLL_INTERVAL)

    logger.info("[Monitor] Thread exiting")


# ── Public API ─────────────────────────────────────────────────────────────────

def clear_all_fingerprints(db_session_factory=None):
    """
    Wipe every stored fingerprint (fp_* config keys) and reset whatsapp_status
    to None on all risk records so the next cycle re-processes and re-sends every
    non-rejected merchant regardless of previous runs.
    """
    from app.db.session import SessionLocal
    from app.models.system_config import SystemConfig
    from app.models.risk_score import RiskScore

    factory = db_session_factory or SessionLocal
    db = factory()
    try:
        deleted = db.query(SystemConfig).filter(SystemConfig.key.like("fp_%")).delete(synchronize_session=False)
        reset = db.query(RiskScore).update({RiskScore.whatsapp_status: None}, synchronize_session=False)
        db.commit()
        logger.info(f"[Monitor] Cache cleared — {deleted} fingerprints deleted, {reset} WA statuses reset")
    except Exception as e:
        logger.error(f"[Monitor] clear_all_fingerprints failed: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()


def start_monitor(db_session_factory=None):
    """Start the background monitor thread (idempotent — won't start twice)."""
    global _monitor_thread, _stop_event

    if _monitor_thread and _monitor_thread.is_alive():
        logger.info("[Monitor] Thread already running — skipping start")
        return

    from app.db.session import SessionLocal
    factory = db_session_factory or SessionLocal

    _stop_event.clear()
    _monitor_thread = threading.Thread(
        target=_monitor_loop,
        args=(factory,),
        daemon=True,
        name="merchant-monitor",
    )
    _monitor_thread.start()
    logger.info("[Monitor] Background thread launched")


def stop_monitor():
    """Signal the background thread to stop after its current cycle."""
    global _stop_event
    _stop_event.set()
    logger.info("[Monitor] Stop signal sent")


def is_running() -> bool:
    return bool(_monitor_thread and _monitor_thread.is_alive())
