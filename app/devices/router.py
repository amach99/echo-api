"""
app/devices/router.py — Device push token registration endpoints.

POST /devices          register a device token (auth required)
DELETE /devices/{token} unregister a device token (auth required)
GET  /devices/me       list my registered devices (auth required, debug use)

Route order: GET /devices/me is registered BEFORE DELETE /devices/{token}
to prevent the literal string "me" being treated as a token value.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_async_db
from app.devices.schemas import DeviceResponse, RegisterDeviceRequest
from app.devices.service import list_user_devices, register_device, unregister_device
from app.models.user import User

router = APIRouter(prefix="/devices", tags=["devices"])


@router.post(
    "",
    response_model=DeviceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a device push token",
)
async def register(
    payload: RegisterDeviceRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> DeviceResponse:
    """
    Register an APNs or FCM device token for the authenticated user.
    Safe to call on every app launch — idempotent upsert by token value.
    """
    device = await register_device(
        user=current_user,
        token=payload.token,
        platform=payload.platform,
        db=db,
    )
    return DeviceResponse.model_validate(device)


@router.get(
    "/me",
    response_model=list[DeviceResponse],
    summary="List my registered devices",
)
async def list_my_devices(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> list[DeviceResponse]:
    """Returns all devices currently registered to the authenticated user."""
    devices = await list_user_devices(user=current_user, db=db)
    return [DeviceResponse.model_validate(d) for d in devices]


@router.delete(
    "/{token}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unregister a device push token",
)
async def unregister(
    token: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> None:
    """
    Remove a device token so this device no longer receives push notifications.
    Typically called on logout.
    """
    await unregister_device(user=current_user, token=token, db=db)
