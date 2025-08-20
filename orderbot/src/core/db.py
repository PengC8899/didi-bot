from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine, AsyncEngine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import StaticPool
from sqlalchemy import event

from ..utils.logging import log_info, log_error


class Base(DeclarativeBase):
    pass


_engine: Optional[AsyncEngine] = None
_Session: Optional[async_sessionmaker[AsyncSession]] = None
_db_lock = asyncio.Lock()


def _configure_sqlite_pragmas(dbapi_connection, connection_record):
    """配置SQLite性能优化参数"""
    with dbapi_connection.cursor() as cursor:
        # 启用WAL模式以提高并发性能
        cursor.execute("PRAGMA journal_mode=WAL")
        # 设置同步模式为NORMAL以平衡性能和安全性
        cursor.execute("PRAGMA synchronous=NORMAL")
        # 设置缓存大小（以页为单位，每页通常4KB）
        cursor.execute("PRAGMA cache_size=10000")
        # 设置临时存储为内存
        cursor.execute("PRAGMA temp_store=MEMORY")
        # 启用外键约束
        cursor.execute("PRAGMA foreign_keys=ON")
        # 设置忙等待超时（毫秒）
        cursor.execute("PRAGMA busy_timeout=30000")


async def init_engine(database_url: str, max_retries: int = 3) -> None:
    """Initialize async engine, sessionmaker and create tables with retry mechanism."""
    global _engine, _Session
    
    async with _db_lock:
        if _engine is not None:
            log_info("db.engine.already_initialized")
            return
        
        retry_count = 0
        while retry_count < max_retries:
            try:
                # 配置数据库引擎参数
                engine_kwargs = {
                    "echo": False,
                    "future": True,
                    "pool_pre_ping": True,  # 连接前检查连接是否有效
                    "pool_recycle": 3600,   # 连接回收时间（秒）
                    "connect_args": {
                        "timeout": 30,  # 连接超时
                        "check_same_thread": False,  # SQLite允许多线程
                    }
                }
                
                # 如果是SQLite，添加特殊配置
                if database_url.startswith(("sqlite", "sqlite+aiosqlite")):
                    engine_kwargs.update({
                        "poolclass": StaticPool,
                    })
                else:
                    # PostgreSQL或其他数据库的连接池配置
                    engine_kwargs.update({
                        "pool_size": 10,        # 连接池大小
                        "max_overflow": 20,     # 最大溢出连接数
                        "pool_timeout": 30,     # 获取连接超时
                    })
                
                _engine = create_async_engine(database_url, **engine_kwargs)
                
                # 为SQLite配置性能优化参数
                if database_url.startswith(("sqlite", "sqlite+aiosqlite")):
                    event.listen(_engine.sync_engine, "connect", _configure_sqlite_pragmas)
                
                _Session = async_sessionmaker(
                    bind=_engine,
                    expire_on_commit=False,
                    class_=AsyncSession
                )
                
                # 测试连接并创建表
                async with _engine.begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)
                
                log_info("db.engine.initialized", database_url=database_url.split("://")[0] + "://***")
                break
                
            except Exception as e:
                retry_count += 1
                log_error("db.init.error", error=str(e), retry_count=retry_count, max_retries=max_retries)
                
                if retry_count >= max_retries:
                    log_error("db.init.max_retries_reached")
                    raise
                
                # 等待后重试
                await asyncio.sleep(min(2 ** retry_count, 10))


async def close_engine() -> None:
    """Close database engine and cleanup resources."""
    global _engine, _Session
    
    async with _db_lock:
        if _engine is not None:
            try:
                await _engine.dispose()
                log_info("db.engine.closed")
            except Exception as e:
                log_error("db.engine.close_error", error=str(e))
            finally:
                _engine = None
                _Session = None


@asynccontextmanager
async def get_session():
    """Get database session with automatic retry and error handling."""
    if _Session is None:
        raise RuntimeError("DB engine not initialized. Call init_engine() first.")
    
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        session = _Session()
        try:
            yield session
            await session.commit()
            break
        except Exception as e:
            await session.rollback()
            retry_count += 1
            
            log_error("db.session.error", error=str(e), retry_count=retry_count, max_retries=max_retries)
            
            if retry_count >= max_retries:
                raise
            
            # 短暂等待后重试
            await asyncio.sleep(0.5 * retry_count)
        finally:
            await session.close()


async def health_check() -> bool:
    """Check database connection health."""
    try:
        async with get_session() as session:
            # 执行简单查询测试连接
            result = await session.execute("SELECT 1")
            result.scalar()
            return True
    except Exception as e:
        log_error("db.health_check.failed", error=str(e))
        return False
