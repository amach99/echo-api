import uuid
from typing import Literal
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.dependencies import get_current_user
from app.database import get_async_db
from app.middleware.age_verification import require_age_verified
from app.models.user import User
from app.votes.service import cast_vote, remove_vote

router = APIRouter(prefix="/votes", tags=["votes"],
                   dependencies=[Depends(require_age_verified)])


class VoteCreate(BaseModel):
    post_id: uuid.UUID
    vote_value: Literal[1, -1]


@router.post("", status_code=status.HTTP_201_CREATED)
async def vote(payload: VoteCreate,
               current_user: User = Depends(get_current_user),
               db: AsyncSession = Depends(get_async_db)) -> dict:
    """Cast or update a vote on a Pulse post. +1 = upvote, -1 = downvote."""
    v = await cast_vote(current_user, payload.post_id, payload.vote_value, db)
    return {"post_id": str(v.post_id), "vote_value": v.vote_value}


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unvote(post_id: uuid.UUID,
                 current_user: User = Depends(get_current_user),
                 db: AsyncSession = Depends(get_async_db)) -> None:
    await remove_vote(current_user, post_id, db)
