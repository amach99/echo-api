"""app/devices/schemas.py — Pydantic schemas for device token endpoints."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class RegisterDeviceRequest(BaseModel):
    token: str = Field(min_length=32, max_length=512, description="APNs or FCM device token")
    platform: Literal["apns", "fcm"]


class DeviceResponse(BaseModel):
    device_id: uuid.UUID
    token: str
    platform: str
    created_at: datetime
    last_seen_at: datetime

    model_config = {"from_attributes": True}
