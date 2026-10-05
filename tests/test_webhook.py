import asyncio

from sqlalchemy import text

from app.db.session import engine


def payload(user_id: int, payment_id: str = "pay_1", status: str = "CONFIRMED") -> dict:
    return {"payment_id": payment_id, "user_id": user_id, "amount": 990, "status": status}


async def count(table: str) -> int:
    async with engine.connect() as conn:
        return (await conn.execute(text(f"SELECT count(*) FROM {table}"))).scalar_one()


async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_confirmed_payment_activates_subscription(client, user_id):
    response = await client.post("/webhook/payment", json=payload(user_id))

    assert response.status_code == 200
    assert response.json() == {"payment_id": "pay_1", "result": "processed"}
    async with engine.connect() as conn:
        status = (
            await conn.execute(
                text("SELECT status FROM subscriptions WHERE user_id = :u"), {"u": user_id}
            )
        ).scalar_one()
    assert status == "active"


async def test_repeated_delivery_is_processed_once(client, user_id):
    first = await client.post("/webhook/payment", json=payload(user_id))
    second = await client.post("/webhook/payment", json=payload(user_id))

    assert first.json()["result"] == "processed"
    assert second.json()["result"] == "already_processed"
    assert await count("payments") == 1
    assert await count("subscriptions") == 1


async def test_concurrent_duplicates_create_one_payment(client, user_id):
    responses = await asyncio.gather(
        *(client.post("/webhook/payment", json=payload(user_id)) for _ in range(10))
    )

    results = sorted(r.json()["result"] for r in responses)
    assert results.count("processed") == 1
    assert results.count("already_processed") == 9
    assert await count("payments") == 1


async def test_second_payment_extends_existing_subscription(client, user_id):
    await client.post("/webhook/payment", json=payload(user_id, "pay_1"))
    response = await client.post("/webhook/payment", json=payload(user_id, "pay_2"))

    assert response.json()["result"] == "processed"
    assert await count("payments") == 2
    assert await count("subscriptions") == 1


async def test_unconfirmed_payment_is_ignored(client, user_id):
    response = await client.post("/webhook/payment", json=payload(user_id, status="PENDING"))

    assert response.json()["result"] == "ignored"
    assert await count("payments") == 0
    assert await count("subscriptions") == 0


async def test_invalid_payload_is_rejected(client, user_id):
    response = await client.post(
        "/webhook/payment", json={**payload(user_id), "payment_id": "   ", "amount": 0}
    )

    assert response.status_code == 422
    assert await count("payments") == 0
