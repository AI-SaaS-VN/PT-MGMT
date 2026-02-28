"""
数据库连接模块

使用 SQLAlchemy 2.0 异步引擎（asyncpg 驱动）。
提供：
  - engine：异步引擎（连接池）
  - AsyncSessionLocal：异步 Session 工厂
  - get_db()：FastAPI 依赖，产生 AsyncSession 并在请求结束后自动关闭

用法（在 FastAPI 路由中）：
    from app.core.database import get_db
    async def my_route(db: AsyncSession = Depends(get_db)):
        ...
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

# -----------------------------------------------------------------------
# 异步引擎
# pool_size=10, max_overflow=20 适合 Phase 1 规模（4-8 技师，300-500 客户）
# echo=True 只在开发环境输出 SQL，生产环境关闭
# -----------------------------------------------------------------------
engine = create_async_engine(
    settings.async_database_url,
    echo=settings.APP_DEBUG and not settings.is_production,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,   # 检测断开的连接，防止 "server closed the connection unexpectedly"
)

# -----------------------------------------------------------------------
# Session 工厂
# expire_on_commit=False：提交后对象仍可访问属性（异步场景下避免 lazy load 报错）
# -----------------------------------------------------------------------
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI 依赖函数，产生一个数据库 Session。

    Session 在 try 块内使用；无论成功或异常都会在 finally 中关闭。
    事务由调用方手动提交（`await db.commit()`）或回滚，
    不使用自动提交，以配合行锁（SELECT ... FOR UPDATE）正确工作。
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
