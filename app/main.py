from fastapi import FastAPI
from app.api.routes import router

app = FastAPI(
    title="Grabon AI Merchant Underwriting Agent",
    description="Production-grade FastAPI application for merchant underwriting",
    version="1.0.0"
)

app.include_router(router)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
