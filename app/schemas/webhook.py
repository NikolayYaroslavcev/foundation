from pydantic import BaseModel, Field, field_validator


class PaymentWebhookRequest(BaseModel):
    payment_id: str = Field(min_length=1)
    user_id: int = Field(gt=0)
    amount: int = Field(gt=0)
    status: str = Field(min_length=1)

    @field_validator("payment_id", "status")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class PaymentWebhookResponse(BaseModel):
    payment_id: str
    result: str
