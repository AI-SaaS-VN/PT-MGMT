# PT-MGMT 项目开发指南（供 Claude Code 使用）

## 项目概述

物理疗法门店管理系统，单体仓库（monorepo）。
- **文档**：`docs/architecture.md`（系统设计）、`tech-stack.md`（技术选型）
- **当前阶段**：Phase 1 — 后端 API + 微信小程序

---

## 目录结构

```
PT-MGMT/
├── backend/                # FastAPI 后端
│   ├── app/
│   │   ├── core/           # config, database, security, wechat
│   │   ├── models/         # SQLAlchemy ORM 模型
│   │   ├── schemas/        # Pydantic 请求/响应 Schema
│   │   ├── routers/        # 路由（按模块拆分）
│   │   ├── deps.py         # FastAPI 依赖注入
│   │   └── main.py         # 应用入口
│   ├── db_migrations/      # Alembic 迁移目录（原 alembic/）
│   │   └── versions/       # 迁移脚本
│   ├── alembic.ini         # Alembic 配置（script_location = backend/db_migrations）
│   ├── .env                # 本地开发环境变量（不提交 Git）
│   ├── requirements.txt
│   └── requirements-dev.txt
├── docker-compose.yml      # 本地开发基础设施（PostgreSQL 16 + Redis 7）
├── docs/
│   └── architecture.md
├── tech-stack.md
└── venv/                   # Python 虚拟环境（项目根目录）
```

---

## 快速启动

所有命令均在**项目根目录** `/home/franc/CC-Prj/PT-MGMT/` 执行。

### 1. 启动基础设施

```bash
sudo docker compose up -d
# 等待 db / redis 状态变为 healthy
sudo docker compose ps
```

### 2. 激活虚拟环境

```bash
source venv/bin/activate
```

### 3. 数据库迁移

```bash
# 查看当前版本
PYTHONPATH=backend alembic -c backend/alembic.ini current

# 升级到最新版本
PYTHONPATH=backend alembic -c backend/alembic.ini upgrade head

# 回滚一步
PYTHONPATH=backend alembic -c backend/alembic.ini downgrade -1
```

### 4. 启动 FastAPI 服务

```bash
# 开发模式（热重载）
PYTHONPATH=backend uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 验证
curl http://localhost:8000/health
# API 文档（开发模式）
# http://localhost:8000/docs
```

---

## 关键约定

### PYTHONPATH 要求

后端所有 Python 命令（uvicorn、alembic、pytest 等）**必须**在命令前加
`PYTHONPATH=backend`，原因：`app/` 包在 `backend/` 目录下，而命令从项目根目录执行。

```bash
# ✓ 正确
PYTHONPATH=backend uvicorn app.main:app ...
PYTHONPATH=backend alembic -c backend/alembic.ini ...
PYTHONPATH=backend pytest backend/tests/

# ✗ 错误（ModuleNotFoundError: No module named 'app'）
uvicorn app.main:app ...
```

### 迁移脚本目录

迁移脚本位于 `backend/db_migrations/versions/`，**不是** `backend/alembic/`。
`alembic.ini` 中 `script_location = backend/db_migrations`。

### 环境变量加载

- 本地开发：`backend/.env`（由 `db_migrations/env.py` 通过 `python-dotenv` 自动加载）
- CI / 生产：直接注入环境变量，不使用 `.env` 文件

### 数据库连接 URL

`backend/.env` 中的 `DATABASE_URL` 格式为 `postgresql://`（不含 `+asyncpg`），
`config.py` 的 `async_database_url` 属性负责自动转换为 `postgresql+asyncpg://`。

### 货币 / 金额字段

所有金额字段均以**分（fen）**为单位存储整数，避免浮点精度问题。

### 软删除

- 软删除：`deleted_at IS NOT NULL`，查询时须过滤 `.where(Model.deleted_at.is_(None))`
- `Transaction` 表无软删除（财务记录永久保留）

---

## 已修复的已知问题

| 错误 | 原因 | 修复方式 |
|---|---|---|
| `TypeError: got 'comment'` | `Index(...)` 不支持 `comment=` 参数 | 改为 Python 注释 |
| `Could not parse SQLAlchemy URL from ''` | `env.py` 未加载 `.env` | `load_dotenv(Path(__file__).parent.parent / ".env")` |
| `invalid input syntax for type json` | `server_default="'{}'::jsonb"` 被双重转义 | 改为 `sa.text("'{}'::jsonb")` |
