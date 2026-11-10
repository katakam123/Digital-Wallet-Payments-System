from pydantic import BaseModel, Field


class FraudDecisionSchema(BaseModel):
    decision_reason: str | None = Field(
        default=None,
        min_length=3,
        max_length=500,
        description="Reason for the Admin decision",
    )