from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    payment_id: str
    user_id: int
    amount: int
    status: str
    created_at: datetime
