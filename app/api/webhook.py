from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.webhook import PaymentWebhookRequest, PaymentWebhookResponse
from app.services.webhook import process_payment_webhook

router = APIRouter()


@router.post("/webhook/payment", response_model=PaymentWebhookResponse)
async def payment_webhook(
    payload: PaymentWebhookRequest,
    session: AsyncSession = Depends(get_db),
) -> PaymentWebhookResponse:
    return await process_payment_webhook(session, payload)
