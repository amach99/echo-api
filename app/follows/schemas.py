import uuid
from datetime import datetime
from pydantic import BaseModel


class FollowCreate(BaseModel):
    following_id: uuid.UUID


class FollowResponse(BaseModel):
    follower_id: uuid.UUID
    following_id: uuid.UUID
    created_at: datetime
    model_config = {"from_attributes": True}
