from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from app.api.routes import router
from app.api.dashboard import router as dashboard_router
from app.api.admin import router as admin_router
from app.db.init_db import init_db
import logging

load_dotenv()

# Configure logging so monitor thread output appears in the server console
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()

    # Restore ALWAYS_ON monitor if it was running before restart
    try:
        from app.db.session import SessionLocal
        from app.services.config_service import get_config
        from app.services import monitor_service
        db = SessionLocal()
        try:
            state = get_config(db, "engine_state", "OFF")
        finally:
            db.close()

        if state == "ALWAYS_ON":
            logger.info("[Startup] engine_state=ALWAYS_ON — resuming background monitor")
            monitor_service.start_monitor()
        else:
            logger.info(f"[Startup] engine_state={state} — monitor not auto-started")
    except Exception as e:
        logger.warning(f"[Startup] Could not check engine state: {e}")

    yield

    # Graceful shutdown
    try:
        from app.services import monitor_service
        monitor_service.stop_monitor()
    except Exception:
        pass


app = FastAPI(
    title="Grabon AI Merchant Underwriting Agent",
    description="Production-grade FastAPI application for merchant underwriting",
    version="1.0.0",
    lifespan=lifespan,
)

# Mount static files and templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# Make templates globally available
app.state.templates = templates

app.include_router(router)
app.include_router(dashboard_router)
app.include_router(admin_router)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
