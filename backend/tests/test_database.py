"""Tests for app.core.database — engine creation, pragma setup, get_db."""

import contextlib
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db


class TestBase:
    def test_base_is_declarative_base(self):
        """Base should be a SQLAlchemy DeclarativeBase subclass."""
        from sqlalchemy.orm import DeclarativeBase

        assert issubclass(Base, DeclarativeBase)

    def test_base_has_metadata(self):
        """Base should have a metadata attribute."""
        assert hasattr(Base, "metadata")


class TestEngineCreation:
    def test_engine_exists(self):
        """Module-level engine should be created."""
        from app.core.database import engine

        assert engine is not None

    def test_engine_is_async(self):
        """Engine should be an async engine."""
        from sqlalchemy.ext.asyncio import AsyncEngine

        from app.core.database import engine

        assert isinstance(engine, AsyncEngine)

    def test_async_session_factory_exists(self):
        """Module-level async_session should be created."""
        from app.core.database import async_session

        assert async_session is not None


class TestSqlitePragma:
    def test_pragma_function_executes(self):
        """_set_sqlite_pragma should execute PRAGMA statements."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        # Import and call the pragma function directly
        from app.core.database import _set_sqlite_pragma

        _set_sqlite_pragma(mock_conn, None)

        # Should have created a cursor
        mock_conn.cursor.assert_called_once()
        # Should have executed PRAGMA statements
        assert mock_cursor.execute.call_count >= 4
        # Verify specific pragmas
        calls = [str(c) for c in mock_cursor.execute.call_args_list]
        assert any("foreign_keys" in c for c in calls)
        assert any("journal_mode" in c for c in calls)
        assert any("busy_timeout" in c for c in calls)
        assert any("synchronous" in c for c in calls)
        # Should have closed the cursor
        mock_cursor.close.assert_called_once()


class TestGetDb:
    @pytest.mark.asyncio
    async def test_get_db_yields_session(self):
        """get_db should yield an AsyncSession."""

        gen = get_db()
        assert isinstance(gen, AsyncGenerator)

        session = await gen.__anext__()
        assert isinstance(session, AsyncSession)

        # Clean up
        with contextlib.suppress(StopAsyncIteration):
            await gen.__anext__()

    @pytest.mark.asyncio
    async def test_get_db_rollback_on_exception(self):
        """get_db should rollback and re-raise on exception."""
        # Create a mock session that simulates the async context manager
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.rollback = AsyncMock()
        mock_session.close = AsyncMock()

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("app.core.database.async_session", return_value=mock_ctx):
            gen = get_db()
            session = await gen.__anext__()
            assert session is mock_session

            # Simulate an exception by throwing into the generator
            with pytest.raises(RuntimeError, match="test error"):
                await gen.athrow(RuntimeError, RuntimeError("test error"))

            mock_session.rollback.assert_awaited_once()
            mock_session.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_db_closes_session_on_normal_exit(self):
        """get_db should close session in finally block."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.close = AsyncMock()

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("app.core.database.async_session", return_value=mock_ctx):
            gen = get_db()
            await gen.__anext__()

            # Normal exit (StopAsyncIteration)
            with contextlib.suppress(StopAsyncIteration):
                await gen.__anext__()

            mock_session.close.assert_awaited_once()


class TestEngineWithLiveDb:
    """Integration tests using a real SQLite database."""

    @pytest.fixture
    async def test_engine(self):
        """Create a temporary test engine."""
        eng = create_async_engine("sqlite+aiosqlite://", echo=False)

        @event.listens_for(eng.sync_engine, "connect")
        def _pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA cache_size=-64000")
            cursor.close()

        yield eng
        await eng.dispose()

    @pytest.mark.asyncio
    async def test_pragma_foreign_keys_enabled(self, test_engine):
        """PRAGMA foreign_keys should be ON."""
        async with test_engine.connect() as conn:
            result = await conn.execute(text("PRAGMA foreign_keys"))
            value = result.scalar()
            assert value == 1

    @pytest.mark.asyncio
    async def test_pragma_busy_timeout(self, test_engine):
        """PRAGMA busy_timeout should be set."""
        async with test_engine.connect() as conn:
            result = await conn.execute(text("PRAGMA busy_timeout"))
            value = result.scalar()
            assert value == 5000

    @pytest.mark.asyncio
    async def test_pragma_synchronous(self, test_engine):
        """PRAGMA synchronous should be NORMAL (1)."""
        async with test_engine.connect() as conn:
            result = await conn.execute(text("PRAGMA synchronous"))
            value = result.scalar()
            assert value == 1  # NORMAL = 1

    @pytest.mark.asyncio
    async def test_session_can_query(self, test_engine):
        """Sessions created by the factory can execute queries."""
        factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            result = await session.execute(text("SELECT 1"))
            assert result.scalar() == 1
