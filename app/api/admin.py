"""
Admin routes: engine trigger and global config.
"""

import logging
from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.engine_service import EngineService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/run-engine")
def run_engine(db: Session = Depends(get_db)):
    """
    Trigger batch underwriting for all merchants (max 10).

    - Runs deterministic risk engine + AI explanation for each merchant
    - Sends WhatsApp offers automatically if AUTO mode is ON
    - Skips merchants with empty/invalid mobile numbers (no crash)
    - Saves engine run summary to DB for dashboard display
    - Redirects to dashboard with ?engine=done
    """
    logger.info("[Admin] Start Underwriting Engine triggered")

    try:
        stats = EngineService.run_all_merchants(db)
        logger.info(f"[Admin] Engine finished: {stats}")
    except Exception as e:
        logger.error(f"[Admin] Engine run failed: {e}", exc_info=True)

    return RedirectResponse(url="/dashboard/?engine=done", status_code=303)
