from datetime import datetime, timedelta, timezone

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import Payment
from app.models.subscription import Subscription
from app.schemas.webhook import PaymentWebhookRequest, PaymentWebhookResponse

CONFIRMED_STATUS = "CONFIRMED"
ACTIVE_SUBSCRIPTION_STATUS = "active"
SUBSCRIPTION_PERIOD = timedelta(days=30)


async def process_payment_webhook(
    session: AsyncSession, payload: PaymentWebhookRequest
) -> PaymentWebhookResponse:
    if payload.status != CONFIRMED_STATUS:
        return PaymentWebhookResponse(payment_id=payload.payment_id, result="ignored")

    expires_at = datetime.now(timezone.utc) + SUBSCRIPTION_PERIOD

    async with session.begin():
        insert_payment = (
            pg_insert(Payment)
            .values(
                payment_id=payload.payment_id,
                user_id=payload.user_id,
                amount=payload.amount,
                status=payload.status,
            )
            .on_conflict_do_nothing(index_elements=["payment_id"])
        )
        result = await session.execute(insert_payment)

        if result.rowcount == 0:
            return PaymentWebhookResponse(payment_id=payload.payment_id, result="already_processed")

        activate_subscription = (
            pg_insert(Subscription)
            .values(
                user_id=payload.user_id,
                status=ACTIVE_SUBSCRIPTION_STATUS,
                expires_at=expires_at,
            )
            .on_conflict_do_update(
                index_elements=["user_id"],
                set_={"status": ACTIVE_SUBSCRIPTION_STATUS, "expires_at": expires_at},
            )
        )
        await session.execute(activate_subscription)

    return PaymentWebhookResponse(payment_id=payload.payment_id, result="processed")
