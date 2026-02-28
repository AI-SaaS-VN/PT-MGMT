"""
Alembic 迁移环境配置

支持：
  - online 模式（alembic upgrade head / downgrade）：异步引擎，实际连接数据库
  - offline 模式（alembic upgrade head --sql）：生成 SQL 脚本，不需要数据库连接

异步支持说明：
  SQLAlchemy 2.0 + asyncpg 需要通过 run_sync 在异步上下文中运行 Alembic 迁移。
  使用 create_async_engine + AsyncConnection.run_sync(do_run_migrations) 模式。

导入所有模型：
  `from app.models import *` 触发所有模型模块的导入，
  从而将所有表注册到 Base.metadata，使 Alembic autogenerate 能感知所有表结构。
"""

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

# ---- 导入所有 ORM 模型（必须，Alembic 才能发现表） ----
from app.models import Base  # noqa: F401  — 导入即注册所有子模型到 metadata
from app.models import *  # noqa: F401, F403

# -----------------------------------------------------------------------
# Alembic Config 对象（包含 alembic.ini 中的配置）
# -----------------------------------------------------------------------
config = context.config

# 配置 Python 日志（读取 alembic.ini 的 [loggers] 部分）
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 目标 metadata：Alembic autogenerate 对比用
target_metadata = Base.metadata


# -----------------------------------------------------------------------
# 数据库 URL：从环境变量读取（不硬编码到 ini 文件）
# -----------------------------------------------------------------------

def get_url() -> str:
    """
    读取数据库连接 URL。

    优先顺序：
      1. 环境变量 DATABASE_URL（CI / 容器注入）
      2. alembic.ini 中的 sqlalchemy.url（本地调试备用）

    URL 自动替换为 asyncpg 驱动格式：
      postgresql://... → postgresql+asyncpg://...
    """
    url = os.environ.get("DATABASE_URL") or config.get_main_option("sqlalchemy.url", "")
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


# -----------------------------------------------------------------------
# Offline 模式（生成 SQL 脚本，不实际连接数据库）
# -----------------------------------------------------------------------

def run_migrations_offline() -> None:
    """
    在 offline 模式下运行迁移，输出纯 SQL 语句。

    使用场景：
      alembic upgrade head --sql > migration.sql
      用于 DBA 审查后手动执行，或在无法直连数据库的 CI 环境中生成脚本。
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # 比较选项：检测列类型变化、服务器默认值变化
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# -----------------------------------------------------------------------
# Online 模式（异步，实际执行 DDL）
# -----------------------------------------------------------------------

def do_run_migrations(connection: Connection) -> None:
    """在同步上下文中运行迁移（由 run_migrations_online 通过 run_sync 调用）。"""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """
    在 online 模式下运行迁移。

    使用异步引擎 + NullPool（迁移任务短暂运行，不需要连接池）。
    通过 run_sync 将异步连接转换为同步上下文供 Alembic 使用。
    """
    connectable = create_async_engine(
        get_url(),
        poolclass=pool.NullPool,  # 迁移不需要连接池
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


# -----------------------------------------------------------------------
# 入口：根据模式分发
# -----------------------------------------------------------------------

if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
