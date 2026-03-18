"""
app/media/router.py — S3 presigned URL generation endpoint.

Flow:
  1. Client calls POST /media/presigned-url with content_type + file_size
  2. Server generates a presigned PUT URL (15-min expiry)
  3. Client uploads directly to S3
  4. Client includes the returned media_url in POST /posts
"""

from typing import Literal

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_async_db
from app.media.service import MAX_FILE_SIZE_BYTES, generate_presigned_upload_url
from app.middleware.age_verification import require_age_verified
from app.models.user import User

router = APIRouter(
    prefix="/media",
    tags=["media"],
    dependencies=[Depends(require_age_verified)],
)


class PresignedUrlRequest(BaseModel):
    content_type: Literal["image/jpeg", "image/png", "image/webp", "image/gif", "video/mp4"]
    file_size_bytes: int = Field(gt=0, le=MAX_FILE_SIZE_BYTES)


class PresignedUrlResponse(BaseModel):
    upload_url: str    # PUT to this URL directly from the client
    media_url: str     # include this in PostCreate.media_url after upload
    expires_in: int = 900


@router.post("/presigned-url", response_model=PresignedUrlResponse,
             status_code=status.HTTP_200_OK)
async def get_presigned_url(
    payload: PresignedUrlRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> PresignedUrlResponse:
    """Generate a presigned S3 PUT URL for direct client-to-S3 media upload."""
    upload_url, media_url = await generate_presigned_upload_url(
        current_user.user_id,
        payload.content_type,
        payload.file_size_bytes,
    )
    return PresignedUrlResponse(upload_url=upload_url, media_url=media_url)
