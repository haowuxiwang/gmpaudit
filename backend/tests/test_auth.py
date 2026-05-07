import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock, AsyncMock

import jwt

from app.core.auth import create_access_token, decode_access_token, ALGORITHM, ACCESS_TOKEN_EXPIRE_HOURS
from app.core.config import settings


def test_create_access_token():
    token = create_access_token(data={"sub": "test_user"})
    assert isinstance(token, str)
    assert len(token) > 0


def test_decode_access_token_valid():
    token = create_access_token(data={"sub": "test_user"})
    payload = decode_access_token(token)
    assert payload["sub"] == "test_user"
    assert "exp" in payload


def test_decode_access_token_expired():
    # Create an already-expired token
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    payload = {"sub": "test_user", "exp": past}
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=ALGORITHM)

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        decode_access_token(token)
    assert exc_info.value.status_code == 401


def test_decode_access_token_invalid():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        decode_access_token("invalid.token.string")
    assert exc_info.value.status_code == 401


def test_decode_access_token_wrong_key():
    payload = {"sub": "test_user", "exp": datetime.now(timezone.utc) + timedelta(hours=1)}
    token = jwt.encode(payload, "wrong-key", algorithm=ALGORITHM)

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        decode_access_token(token)
    assert exc_info.value.status_code == 401


def test_token_contains_expiry():
    token = create_access_token(data={"sub": "user1"})
    payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[ALGORITHM])
    assert "exp" in payload
    # Expiry should be in the future
    exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    assert exp > datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_get_current_user_no_token():
    from app.core.auth import get_current_user
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token=None, db=MagicMock())
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_invalid_payload():
    from app.core.auth import get_current_user
    from fastapi import HTTPException

    # Token without 'sub' claim
    token = jwt.encode({"exp": datetime.now(timezone.utc) + timedelta(hours=1)}, settings.JWT_SECRET_KEY, algorithm=ALGORITHM)
    mock_token = MagicMock()
    mock_token.credentials = token

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token=mock_token, db=MagicMock())
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_user_not_found():
    from app.core.auth import get_current_user
    from fastapi import HTTPException

    token = create_access_token(data={"sub": "nonexistent_user"})
    mock_token = MagicMock()
    mock_token.credentials = token

    # Mock DB that returns no user
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token=mock_token, db=mock_db)
    assert exc_info.value.status_code == 401
