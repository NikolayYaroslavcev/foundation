from fastapi import FastAPI

from app.api.v1 import router as api_v1_router
from app.api.webhook import router as webhook_router

app = FastAPI(title="Foundation")

app.include_router(api_v1_router, prefix="/api/v1")
app.include_router(webhook_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
