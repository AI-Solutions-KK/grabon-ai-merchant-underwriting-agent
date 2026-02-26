from fastapi import FastAPI

app = FastAPI(
    title="Grabon AI Merchant Underwriting Agent",
    description="Production-grade FastAPI application for merchant underwriting",
    version="1.0.0"
)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
