from __future__ import annotations

from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


_engine = None
_Session: async_sessionmaker[AsyncSession] | None = None


async def init_engine(database_url: str) -> None:
    """Initialize async engine, sessionmaker and create tables."""
    global _engine, _Session
    _engine = create_async_engine(database_url, echo=False, future=True)
    _Session = async_sessionmaker(bind=_engine, expire_on_commit=False)

    # Create tables
    async with _engine.begin() as conn:  # type: ignore[arg-type]
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def get_session():
    if _Session is None:
        raise RuntimeError("DB engine not initialized. Call init_engine() first.")
    session = _Session()
    try:
        yield session
        await session.commit()
    except Exception:  # noqa: BLE001
        await session.rollback()
        raise
    finally:
        await session.close()
