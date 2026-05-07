import logging
import secrets
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from app.core.config import settings
from app.core.database import get_db
from app.core.auth import create_access_token, get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()

FEISHU_AUTHORIZE_URL = "https://open.feishu.cn/open-apis/authen/v1/authorize"
FEISHU_APP_TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/app_access_token/internal/"
FEISHU_USER_TOKEN_URL = "https://open.feishu.cn/open-apis/authen/v1/oidc/access_token"
FEISHU_USER_INFO_URL = "https://open.feishu.cn/open-apis/authen/v1/user_info"

CSRF_MAX_AGE = 300  # 5 minutes


def _get_csrf_serializer():
    return URLSafeTimedSerializer(settings.JWT_SECRET_KEY)


@router.get("/feishu/login")
async def feishu_login(response: Response):
    state = secrets.token_urlsafe(16)
    serializer = _get_csrf_serializer()
    signed_state = serializer.dumps(state)

    url = (
        f"{FEISHU_AUTHORIZE_URL}"
        f"?app_id={settings.FEISHU_APP_ID}"
        f"&redirect_uri={settings.FEISHU_REDIRECT_URI}"
        f"&state={state}"
    )

    response.set_cookie(
        key="feishu_csrf_state",
        value=signed_state,
        max_age=CSRF_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    logger.info("Feishu login: state generated and cookie set")
    return {"url": url}


@router.get("/feishu/callback")
async def feishu_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(None),
    db: AsyncSession = Depends(get_db),
):
    # CSRF state validation
    cookie_state = request.cookies.get("feishu_csrf_state")
    if not cookie_state or not state:
        logger.warning("Feishu callback: missing CSRF state")
        raise HTTPException(status_code=400, detail="Missing CSRF state")

    serializer = _get_csrf_serializer()
    try:
        expected_state = serializer.loads(cookie_state, max_age=CSRF_MAX_AGE)
    except SignatureExpired:
        logger.warning("Feishu callback: CSRF state expired")
        raise HTTPException(status_code=400, detail="CSRF state expired")
    except BadSignature:
        logger.warning("Feishu callback: invalid CSRF state signature")
        raise HTTPException(status_code=400, detail="Invalid CSRF state")

    if state != expected_state:
        logger.warning("Feishu callback: CSRF state mismatch")
        raise HTTPException(status_code=400, detail="CSRF state mismatch")

    async with httpx.AsyncClient() as client:
        # Step 1: Get app_access_token
        app_token_resp = await client.post(
            FEISHU_APP_TOKEN_URL,
            json={
                "app_id": settings.FEISHU_APP_ID,
                "app_secret": settings.FEISHU_APP_SECRET,
            },
        )
        app_token_data = app_token_resp.json()
        app_access_token = app_token_data.get("app_access_token")
        if not app_access_token:
            raise HTTPException(
                status_code=502,
                detail=f"获取飞书app_access_token失败: {app_token_data.get('msg', 'unknown error')}",
            )

        # Step 2: Exchange code for user_access_token
        user_token_resp = await client.post(
            FEISHU_USER_TOKEN_URL,
            json={"grant_type": "authorization_code", "code": code},
            headers={"Authorization": f"Bearer {app_access_token}"},
        )
        user_token_data = user_token_resp.json()
        data = user_token_data.get("data", {})
        user_access_token = data.get("access_token")
        if not user_access_token:
            raise HTTPException(
                status_code=502,
                detail=f"获取飞书user_access_token失败: {user_token_data.get('msg', 'unknown error')}",
            )

        # Step 3: Get user info
        user_info_resp = await client.get(
            FEISHU_USER_INFO_URL,
            headers={"Authorization": f"Bearer {user_access_token}"},
        )
        user_info_data = user_info_resp.json()
        user_info = user_info_data.get("data", {})
        open_id = user_info.get("open_id")
        if not open_id:
            raise HTTPException(
                status_code=502,
                detail=f"获取飞书用户信息失败: {user_info_data.get('msg', 'unknown error')}",
            )

    # Step 4: Upsert user
    result = await db.execute(select(User).where(User.feishu_open_id == open_id))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            feishu_open_id=open_id,
            name=user_info.get("name"),
            avatar_url=user_info.get("avatar_url"),
            email=user_info.get("email"),
            last_login=datetime.now(timezone.utc),
        )
        db.add(user)
    else:
        user.name = user_info.get("name") or user.name
        user.avatar_url = user_info.get("avatar_url") or user.avatar_url
        user.email = user_info.get("email") or user.email
        user.last_login = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(user)

    # Step 5: Create JWT
    access_token = create_access_token(data={"sub": user.feishu_open_id})

    # Step 6: Return
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "name": user.name,
            "avatar": user.avatar_url,
        },
    }


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "name": current_user.name,
        "avatar": current_user.avatar_url,
        "email": current_user.email,
        "feishu_open_id": current_user.feishu_open_id,
        "last_login": current_user.last_login,
        "created_at": current_user.created_at,
    }
