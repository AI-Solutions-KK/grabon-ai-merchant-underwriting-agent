"""
WhatsApp Messaging Service via Twilio

Handles:
- WhatsApp message sending
- Business-formatted responses
- Delivery status tracking
- Retry logic with exponential backoff
- Error handling and logging
"""

import os
import re
import time
import logging
from typing import Dict, Optional
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

logger = logging.getLogger(__name__)


def normalize_wa_number(number: str) -> str:
    """
    Convert any user-entered phone number into a valid whatsapp:+E.164 string.

    Handles:
    - 10-digit Indian numbers (6-9XXXXXXXXX) → whatsapp:+91XXXXXXXXXX
    - 12-digit Indian (91XXXXXXXXXX)          → whatsapp:+91XXXXXXXXXX
    - Already has +                           → whatsapp:+XXXX
    - Already has whatsapp: prefix            → re-normalised cleanly

    Returns "" if the resulting number has fewer than 7 digits (invalid).
    """
    num = number.strip()

    # Strip existing whatsapp: prefix so we work on just the digits/+
    if num.lower().startswith("whatsapp:"):
        num = num[9:].strip()

    # Remove formatting characters
    num = re.sub(r"[\s\-\(\)\.]+", "", num)

    # 10-digit Indian mobile (starts 6-9)
    if re.match(r"^[6-9]\d{9}$", num):
        num = f"+91{num}"
    # 12-digit with country code 91 but no leading +
    elif re.match(r"^91\d{10}$", num):
        num = f"+{num}"
    # Add leading + if missing
    elif num and not num.startswith("+"):
        num = f"+{num}"

    # Basic sanity — at least 7 digits after +
    digits = re.sub(r"\D", "", num)
    if len(digits) < 7:
        return ""

    return f"whatsapp:{num}"


class WhatsAppServiceException(Exception):
    """Custom exception for WhatsApp service errors"""
    pass


class WhatsAppService:
    """
    Service for sending WhatsApp messages via Twilio.
    
    Features:
    - Retry logic (up to 2 attempts)
    - Delivery status logging
    - Professional message formatting
    - Error handling and graceful degradation
    """
    
    def __init__(self):
        """Initialize Twilio client with credentials"""
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
        self.twilio_number = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")
        
        # Validate credentials
        if not self.account_sid or not self.auth_token:
            logger.warning("Twilio credentials not configured - WhatsApp messages will fail")
        
        try:
            self.client = Client(self.account_sid, self.auth_token)
        except Exception as e:
            logger.error(f"Failed to initialize Twilio client: {e}")
            self.client = None
    
    # Twilio error codes that should NOT be retried — fail immediately
    _NO_RETRY_CODES = {
        20003: "Twilio auth failure — check TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN",
        21211: "Invalid 'To' phone number format",
        21214: "Destination number is not a mobile number",
        21215: "Destination number is not enabled for SMS/WhatsApp",
        21408: "Permission to send to this region is not enabled",
        21610: "Number is blacklisted — unsubscribed from messages",
        21614: "Number is not a valid mobile number",
        63007: "Recipient has not joined the WhatsApp sandbox — ask them to send the join code first",
        63016: "Message blocked by WhatsApp — content policy violation",
        63032: "WhatsApp template must be used for first message to this user",
    }

    def send_message(
        self,
        to_number: str,
        message: str,
        max_retries: int = 2,
        retry_delay: int = 2
    ) -> Dict[str, str]:
        """
        Send WhatsApp message with retry logic and fail-safe error handling.

        NEVER raises an exception — always returns a dict:
            {"sid": str, "status": "queued|sent|delivered|failed", "error": str|None}

        Fail-safe behaviour:
        - Invalid number       → immediate failed, logged, no retry
        - Sandbox not joined   → immediate failed, instructional log message
        - Auth error           → immediate failed, no retry
        - Transient errors     → up to max_retries attempts
        - Any unexpected error → caught, logged, returns failed
        """
        if not self.client:
            logger.warning(f"[WhatsApp] Twilio client not initialised — cannot send to {to_number}")
            return {"sid": "N/A", "status": "failed", "error": "Twilio client not initialised"}

        attempt = 0
        last_error = None

        while attempt < max_retries:
            attempt += 1
            try:
                logger.info(f"[WhatsApp] Sending to {to_number} (attempt {attempt}/{max_retries})")
                msg = self.client.messages.create(
                    from_=self.twilio_number,
                    to=to_number,
                    body=message
                )
                logger.info(f"[WhatsApp] Sent OK | SID: {msg.sid} | Status: {msg.status} | To: {to_number}")
                return {"sid": msg.sid, "status": msg.status, "error": None}

            except TwilioRestException as e:
                last_error = str(e)
                human_reason = self._NO_RETRY_CODES.get(e.code)

                if human_reason:
                    # Known hard-fail — no retry, full user-friendly log
                    logger.error(
                        f"[WhatsApp] Hard failure sending to {to_number} | "
                        f"Code {e.code}: {human_reason}"
                    )
                    return {
                        "sid": "N/A",
                        "status": "failed",
                        "error": f"[{e.code}] {human_reason}"
                    }

                # Transient or unknown Twilio error — retry permitted
                logger.warning(
                    f"[WhatsApp] Twilio error (attempt {attempt}/{max_retries}) | "
                    f"Code {e.code}: {e.msg}"
                )
                if attempt < max_retries:
                    logger.info(f"[WhatsApp] Retrying in {retry_delay}s...")
                    time.sleep(retry_delay)

            except Exception as e:
                last_error = str(e)
                logger.error(f"[WhatsApp] Unexpected error sending to {to_number}: {e}", exc_info=True)
                if attempt < max_retries:
                    logger.info(f"[WhatsApp] Retrying in {retry_delay}s...")
                    time.sleep(retry_delay)

        error_msg = f"Failed after {max_retries} attempts: {last_error}"
        logger.error(f"[WhatsApp] All retries exhausted for {to_number}: {error_msg}")
        return {"sid": "N/A", "status": "failed", "error": error_msg}
    
    def send_underwriting_result(
        self,
        to_number: str,
        merchant_id: str,
        risk_tier: str,
        decision: str,
        risk_score: int,
        explanation: str,
        merchant_name: str = "",
        financial_offer: Optional[Dict] = None,
        secure_offer_link: str = ""
    ) -> Dict[str, str]:
        """
        Send structured underwriting offer notification via WhatsApp.

        Uses the new business-friendly format with credit/insurance details and offer link.
        Does NOT include the AI explanation — that stays in the admin dashboard only.
        """
        message = format_underwriting_message(
            merchant_id=merchant_id,
            merchant_name=merchant_name,
            risk_tier=risk_tier,
            decision=decision,
            risk_score=risk_score,
            financial_offer=financial_offer or {},
            secure_offer_link=secure_offer_link,
        )
        return self.send_message(to_number, message)


def format_underwriting_message(
    merchant_id: str,
    risk_tier: str,
    decision: str,
    risk_score: int,
    merchant_name: str = "",
    financial_offer: Optional[Dict] = None,
    secure_offer_link: str = "",
    # legacy param kept for backward compatibility
    explanation: str = "",
) -> str:
    """
    Structured WhatsApp business notification.

    Format:
        📊 GrabCredit Pre-Approved Offer
        Merchant / Risk Tier / Decision
        💳 Credit section (if present)
        🛡 Insurance section (if present)
        View & Accept link
    """
    offer = financial_offer or {}
    display_name = merchant_name or merchant_id

    lines = [
        "📊 *GrabCredit Pre-Approved Offer*",
        "",
        f"Merchant: {display_name}",
        f"Risk Tier: {risk_tier}",
        f"Decision: {decision}",
        "",
    ]

    credit = offer.get("credit")
    insurance = offer.get("insurance")

    if credit:
        limit_str = f"₹{int(credit.get('credit_limit_lakhs', 0) * 100000):,}"
        rate_str = f"{credit.get('interest_rate_percent', 0)}%"
        tenures = credit.get("tenure_options_months", [])
        tenure_str = (
            f"{min(tenures)}–{max(tenures)} months"
            if len(tenures) > 1
            else (f"{tenures[0]} months" if tenures else "N/A")
        )
        lines += [
            "💳 *GrabCredit Offer*",
            f"  Credit Limit : {limit_str}",
            f"  Interest     : {rate_str} p.a.",
            f"  Tenure       : {tenure_str}",
            "",
        ]

    if insurance:
        cov_str = f"₹{int(insurance.get('coverage_amount_lakhs', 0) * 100000):,}"
        prem_str = f"₹{int(insurance.get('premium_amount', 0)):,}/year"
        lines += [
            "🛡 *GrabInsurance Offer*",
            f"  Coverage : {cov_str}",
            f"  Premium  : {prem_str}",
            "",
        ]

    if not credit and not insurance:
        lines.append("No financial offers available at this time.")
        lines.append("")

    if secure_offer_link:
        lines += [
            "📎 *View & Accept your offer:*",
            secure_offer_link,
            "",
        ]

    lines.append("_Thank you for partnering with Grab._")
    return "\n".join(lines)
