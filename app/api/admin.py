from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import oauth2_scheme
from app.core.security import decode_token
from app.db.session import AsyncSessionLocal
from app.models.user import User
from scripts import seed_db

router = APIRouter(tags=["admin"])


class OperationalResetRequest(BaseModel):
    confirm: bool = False


class OperationalResetResponse(BaseModel):
    status: str
    message: str


async def require_admin_without_request_session(
    token: Annotated[str, Depends(oauth2_scheme)],
) -> User:
    payload = decode_token(token)
    if not payload or not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 토큰입니다.",
        )

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.id == int(payload["sub"])))
        user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="존재하지 않는 유저입니다.",
        )
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="운영자 권한이 필요합니다.",
        )
    return user


@router.post("/admin/reset-operational-data", response_model=OperationalResetResponse)
async def reset_operational_data(
    payload: OperationalResetRequest,
    admin: Annotated[User, Depends(require_admin_without_request_session)],
) -> OperationalResetResponse:
    if not payload.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="데이터 초기화 확인이 필요합니다.",
        )

    await seed_db.reset()
    await seed_db.seed(include_demo_details=False)
    return OperationalResetResponse(
        status="ok",
        message="운영 데이터 초기화가 완료되었습니다.",
    )
