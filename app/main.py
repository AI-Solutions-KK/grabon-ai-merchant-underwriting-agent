from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from app.api.routes import router
from app.api.dashboard import router as dashboard_router
from app.api.admin import router as admin_router
from app.db.init_db import init_db

# Load environment variables from .env file
load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


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
