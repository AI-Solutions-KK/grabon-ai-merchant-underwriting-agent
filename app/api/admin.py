"""
Admin routes: engine trigger and global config.
"""

import logging
from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.engine_service import EngineService
from app.services.config_service import set_config
from app.services import monitor_service
from app.services.monitor_service import clear_all_fingerprints

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


def _run_once_and_store(db: Session):
    """
    Synchronously run one full cycle and persist stats to DB.
    Called directly from endpoint handlers — no background thread involved.
    """
    import json as _json
    from app.db.session import SessionLocal
    from app.services.monitor_service import _run_cycle

    monitor_service.stop_monitor()     # stop any existing background run first
    clear_all_fingerprints()           # wipe cache so every merchant is re-processed
    set_config(db, "engine_state", "OFF")  # mark as OFF immediately (single run)

    stats = _run_cycle(SessionLocal)   # blocks until all merchants processed + WA sent

    # Persist stats so dashboard banner can display them
    set_config(db, "last_engine_summary", _json.dumps(stats))
    logger.info(f"[Admin] Single run complete: {stats}")
    return stats


@router.post("/run-engine")
def run_engine(db: Session = Depends(get_db)):
    """Legacy endpoint — kept for compatibility. Runs synchronously."""
    logger.info("[Admin] /run-engine triggered")
    _run_once_and_store(db)
    return RedirectResponse(url="/dashboard/?engine=done", status_code=303)


@router.post("/engine/on")
def engine_on(db: Session = Depends(get_db)):
    """
    RUN ONCE — synchronously process every merchant, send WA, show results.
    Clears cache first so every non-rejected merchant always gets a message.
    """
    logger.info("[Admin] Engine ON — synchronous single run")
    _run_once_and_store(db)
    return RedirectResponse(url="/dashboard/?engine=done", status_code=303)


@router.post("/engine/always-on")
def engine_always_on(db: Session = Depends(get_db)):
    """
    ALWAYS ON — start continuous background monitoring.
    Clears cache first so first cycle re-sends to all non-rejected merchants.
    Subsequent cycles only re-send when data actually changes.
    """
    logger.info("[Admin] Engine ALWAYS ON started — clearing cache first")
    clear_all_fingerprints()          # ensure first cycle sends to everyone
    set_config(db, "engine_state", "ALWAYS_ON")
    monitor_service.stop_monitor()   # restart cleanly
    monitor_service.start_monitor()
    return RedirectResponse(url="/dashboard/?engine=always_on", status_code=303)


@router.post("/engine/clear-cache")
def engine_clear_cache(db: Session = Depends(get_db)):
    """
    Clear all stored fingerprints and reset whatsapp_status on every risk record.
    Does NOT start/stop the engine — just resets the 'already sent' memory so
    the next engine run will re-send WA to all non-rejected merchants.
    """
    logger.info("[Admin] Manual cache clear requested")
    clear_all_fingerprints()
    return RedirectResponse(url="/dashboard/?cache=cleared", status_code=303)


@router.post("/engine/off")
def engine_off(db: Session = Depends(get_db)):
    """
    OFF — stop background monitoring. No more auto-processing.
    """
    logger.info("[Admin] Engine OFF")
    set_config(db, "engine_state", "OFF")
    monitor_service.stop_monitor()
    return RedirectResponse(url="/dashboard/?engine=off", status_code=303)
