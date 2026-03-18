"""
app/media/service.py — AWS S3 presigned URL generation.

Clients upload directly to S3 using the presigned PUT URL.
The returned media_url is then included in the PostCreate payload.

boto3 is synchronous, so calls are offloaded to a thread executor
to keep the async event loop unblocked (Rule 4).
"""

import asyncio
import mimetypes
import uuid
from typing import Literal

import boto3
from botocore.exceptions import ClientError
from fastapi import HTTPException, status

from app.config import get_settings

settings = get_settings()

ALLOWED_CONTENT_TYPES = Literal[
    "image/jpeg", "image/png", "image/webp", "image/gif", "video/mp4"
]
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB

_EXT_MAP: dict[str, str] = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
    "video/mp4": "mp4",
}


def _generate_presigned_url_sync(
    user_id: uuid.UUID,
    content_type: str,
    file_size_bytes: int,
) -> tuple[str, str]:
    """
    Synchronous boto3 call — run inside executor.
    Returns (upload_url, media_url).
    """
    ext = _EXT_MAP.get(content_type, "bin")
    object_key = f"media/{user_id}/{uuid.uuid4()}.{ext}"

    s3 = boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION,
    )

    upload_url: str = s3.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.S3_BUCKET_NAME,
            "Key": object_key,
            "ContentType": content_type,
            "ContentLength": file_size_bytes,
        },
        ExpiresIn=900,  # 15 minutes
    )

    media_url = (
        f"https://{settings.S3_BUCKET_NAME}.s3.{settings.AWS_REGION}.amazonaws.com/{object_key}"
    )
    return upload_url, media_url


async def generate_presigned_upload_url(
    user_id: uuid.UUID,
    content_type: str,
    file_size_bytes: int,
) -> tuple[str, str]:
    """
    Async wrapper — offloads blocking boto3 call to thread executor.
    Returns (upload_url, media_url).
    """
    if content_type not in _EXT_MAP:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "UNSUPPORTED_MEDIA_TYPE",
                "message": f"Allowed types: {', '.join(_EXT_MAP.keys())}",
            },
        )
    if file_size_bytes > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "FILE_TOO_LARGE",
                "message": f"Maximum file size is {MAX_FILE_SIZE_BYTES // (1024*1024)} MB.",
            },
        )

    if settings.AWS_ACCESS_KEY_ID == "PLACEHOLDER":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "MEDIA_UPLOAD_UNAVAILABLE",
                "message": "AWS S3 is not configured. Please provide credentials.",
            },
        )

    loop = asyncio.get_event_loop()
    try:
        upload_url, media_url = await loop.run_in_executor(
            None,
            _generate_presigned_url_sync,
            user_id,
            content_type,
            file_size_bytes,
        )
    except ClientError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "S3_ERROR", "message": str(exc)},
        ) from exc

    return upload_url, media_url
