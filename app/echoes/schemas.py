import uuid
from datetime import datetime
from pydantic import BaseModel


class EchoCreate(BaseModel):
    post_id: uuid.UUID


class EchoResponse(BaseModel):
    echoer_id: uuid.UUID
    post_id: uuid.UUID
    created_at: datetime
    model_config = {"from_attributes": True}
