# 门店App — 技术方案文档
# Physical Therapy Store App — Technical Stack & Architecture

**Version**: 1.0
**Date**: 2026-02-28
**Author**: AI-assisted architecture review
**Related document**: 门店app开发需求.docx

---

## 1. 项目概述 / Project Overview

本项目为一家理疗门店开发管理系统，分两个阶段交付：

- **Phase 1（当前）**: 微信小程序作为主要用户界面，恢复并整理历史客户数据，上线核心业务功能（客户管理、购课、销课、转介绍、通知）。目标客户量：300–500人；技师数量：4–8人。
- **Phase 2（下一版本）**: 增加 Web 网页端，用户可通过浏览器访问相同功能；同时引入 AI 智能诊断功能，与 SOP 服务流程集成。
- **未来**: AI 症状诊断（如骶髂紧张度判断）深度集成。

后端 API 从第一天起就按照**前端无关（client-agnostic）**的 REST API 设计，天然支持多个客户端共用同一套接口。

---

## 2. 技术栈总览 / Tech Stack Overview

### 2.1 客户端层 / Client Layer (Multi-Frontend)

| 客户端 | 阶段 | 技术选型 | 说明 |
|---|---|---|---|
| 微信小程序 | Phase 1（现在） | Taro 4 + React + TypeScript | 编译为原生 WXML/WXSS |
| Web 网页端 | Phase 2（下一版本） | Next.js 14 + App Router + TypeScript | SSR 支持 SEO，复用同一后端 API |
| 管理后台 | Phase 1（现在） | React 18 + Ant Design Pro 5 + Vite | 门店内部管理工具，SPA 即可 |

> **为什么小程序用 Taro 而不是原生开发？**
> Taro 使用 React/TypeScript 语法编写一套代码，编译为微信小程序原生 WXML/WXSS，开发体验更好、类型安全更强，且后续可为其他平台（如 H5）提供基础。

> **为什么 Web 端用 Next.js 而不是 Taro H5 编译？**
> Taro 的 H5 编译产物是移动端优先的小程序风格页面，缺少鼠标/键盘交互体验。Next.js 提供完整的 Web 应用体验（SSR、SEO 友好），且与 Ant Design 生态高度契合。

> **共享类型（Shared Types）**: monorepo 中的 `packages/shared/` 包导出所有 TypeScript 接口（User、Course、Session 等），小程序和 Web 端都从该包导入，避免类型定义漂移。

---

### 2.2 后端 API / Backend API

| 层级 | 选型 | 选择理由 |
|---|---|---|
| 框架 | **Python 3.12 + FastAPI** | 异步原生，自动生成 OpenAPI 文档，Phase 2 AI 友好（Python 是 AI/ML 的首选语言） |
| ORM / 数据库迁移 | **SQLAlchemy 2.0 + Alembic** | Python 事实标准，迁移管理清晰 |
| 微信 SDK | **wechatpy** | 成熟的微信开放平台 SDK（登录、订阅消息、微信支付）|
| 数据校验 | **Pydantic v2** | FastAPI 内置，类型安全强 |
| 异步任务 | **Celery + Redis** | 批量推送通知、大体量 Excel 导出任务 |
| Excel 导入/导出 | **openpyxl** | 客户数据导入及导出需求 |

**API 设计原则**: 后端为纯 REST API（`/api/v1/`），与客户端无关。小程序、Web 端、管理后台均调用同一套接口。认证统一使用 JWT，支持两种登录路径（微信 OAuth 或手机号+短信验证码）。

---

### 2.3 数据库 / Database

| 选型 | 选择理由 |
|---|---|
| **PostgreSQL 15** | 关系型数据库保障财务数据完整性；JSONB 列为 Phase 2 AI 预留弹性字段；TEXT[] 原生数组类型支持身体部位记录 |
| **Redis 7** | 微信 access_token 缓存（微信有频率限制）；Celery 消息队列 broker；SMS 发送频率限制 |

---

### 2.4 部署 / Hosting & Deployment

**云服务商：腾讯云**（首选原因：微信支付回调和微信开放平台 API 在腾讯内网延迟最低；ICP 备案流程相对简便）

| 服务 | 用途 | 预估费用 |
|---|---|---|
| CVM (2 vCPU, 4GB) | Docker Compose 宿主机 | ~280 元/月 |
| TencentDB PostgreSQL | 托管数据库，自动备份 | ~200 元/月 |
| 腾讯云 Redis | 托管缓存 | ~60 元/月 |
| COS | 头像、上传文档、导出 Excel | ~10 元/月 |
| CDN | 管理后台 + Web 端静态资源 | ~20 元/月 |
| **Phase 1 合计** | | **~570 元/月（约 $79 USD）** |

**部署方式：Docker Compose（3 个容器）**

```
api      → FastAPI + Uvicorn（Gunicorn 进程管理）
worker   → Celery（通知推送、大型导出任务）
nginx    → 反向代理、TLS 终止、管理后台静态文件服务
```

PostgreSQL 和 Redis 使用腾讯云托管服务（生产环境），本地开发使用 Docker Compose 一并启动。

---

## 3. 目录结构 / File Structure

### 3.1 Monorepo 根目录

```
pt-mgmt/
├── packages/
│   └── shared/               # 共享 TypeScript 类型定义
│       ├── src/types/
│       └── package.json
├── miniprogram/              # 微信小程序（Taro + React）
├── webapp/                   # Web 网页端（Next.js 14）— Phase 2
├── backend/                  # Python FastAPI 后端
├── admin/                    # 管理后台（React + Ant Design Pro）
├── nginx/                    # Nginx 配置
├── docker-compose.yml        # 本地开发
├── docker-compose.prod.yml   # 生产环境
├── .env.example              # 环境变量模板
└── docs/
    └── tech-stack.md         # 本文档
```

---

### 3.2 共享类型包 `packages/shared/src/types/`

```
user.ts         # User、StaffProfile 接口
course.ts       # Course、CustomerPackage 接口
session.ts      # Session 接口
payment.ts      # Transaction、Coupon 接口
referral.ts     # Referral 接口
api.ts          # 公共 API 响应类型（PaginatedResponse<T> 等）
```

---

### 3.3 微信小程序 `miniprogram/src/`

```
├── app.tsx / app.config.ts / app.less
├── pages/
│   ├── index/                # 首页 / 仪表盘
│   ├── login/                # 微信登录落地页
│   ├── profile/              # 客户个人信息
│   ├── packages/             # list（套餐列表）/ detail（套餐详情）/ my-packages（我的课包）
│   ├── sessions/             # list（上课记录）/ detail（单次记录）
│   ├── payment/              # wechat-pay（微信支付）/ bank-transfer（转账说明）
│   ├── referral/             # 转介绍码 + 奖励状态
│   └── notifications/        # 订阅消息授权
├── components/               # PackageCard、SessionCard、PaymentModal、ReferralBanner…
├── store/                    # Zustand 状态：auth、customer、package
├── services/                 # api.ts 基础封装 + 各资源 service 文件
├── utils/
│   ├── wx-login.ts           # wx.login → 后端 code 换 JWT 流程封装
│   ├── subscribe-message.ts  # wx.requestSubscribeMessage 封装
│   └── format.ts             # 日期、金额（人民币）格式化
└── types/                    # 从 packages/shared 重导出
```

---

### 3.4 Web 端 `webapp/`（Phase 2，Next.js 14 App Router）

```
├── app/
│   ├── layout.tsx
│   ├── page.tsx              # 落地页 / 重定向至登录
│   ├── (auth)/
│   │   └── login/page.tsx    # 手机号 + 短信验证码登录，微信扫码选项
│   ├── dashboard/page.tsx    # 仪表盘
│   ├── packages/
│   │   ├── page.tsx          # 套餐目录
│   │   └── [id]/page.tsx     # 套餐详情 + 购买
│   ├── sessions/page.tsx     # 上课记录
│   ├── profile/page.tsx      # 个人信息
│   └── referral/page.tsx     # 转介绍
├── components/               # Web 端 UI（shadcn/ui 或 Ant Design）
├── lib/
│   ├── api.ts                # Axios/fetch 客户端 + JWT 注入
│   └── auth.ts               # Next.js 会话管理（next-auth 或 jose）
└── types/                    # 从 packages/shared 重导出
```

---

### 3.5 后端 API `backend/app/`（单人开发简化版）

```
├── main.py                   # FastAPI 工厂函数、中间件、CORS
├── config.py                 # Pydantic Settings（环境变量）
├── deps.py                   # FastAPI Depends()：数据库 session、当前用户
├── routers/
│   ├── auth.py               # 微信登录、手机号+短信登录、JWT 刷新
│   ├── customers.py          # CRUD + Excel 导入接口
│   ├── staff.py              # 技师管理
│   ├── courses.py            # 套餐/课程目录管理
│   ├── packages.py           # 客户购课、课包余额
│   ├── sessions.py           # 销课记录、佣金计算
│   ├── payments.py           # 微信支付下单、银行转账确认
│   ├── referrals.py          # 转介绍管理
│   ├── notifications.py      # 订阅消息推送
│   └── export.py             # Excel 导出
├── webhooks/
│   ├── wechat_pay.py         # 微信支付异步回调
│   └── wechat_msg.py         # 微信消息事件处理
├── core/
│   ├── security.py           # JWT 编解码、短信验证码校验
│   └── wechat.py             # WeChatPy 单例（登录、支付、消息）
├── models/                   # SQLAlchemy ORM 模型（见第 4 节）
├── schemas/                  # Pydantic 请求/响应 Schema
├── tasks.py                  # Celery 异步任务（通知、大型导出）
└── db/                       # engine.py + Alembic 迁移文件
```

> **单人开发简化说明**: 业务逻辑直接写在 router 文件中，无需独立的 `services/` 层。当某个 router 文件超过 200 行或多个路由共享同一段逻辑时，再提取为独立 service 模块。

---

### 3.6 管理后台 `admin/src/`

```
├── pages/
│   ├── dashboard/            # KPI 汇总：今日上课数、活跃客户数、待收款、本月营收
│   ├── customers/
│   │   ├── list.tsx          # ProTable 列表 + 搜索筛选 + Excel 导入按钮
│   │   ├── detail.tsx        # 客户详情：档案、课包、上课记录、付款记录
│   │   ├── form.tsx          # 新增/编辑（手动录入）
│   │   └── import.tsx        # Excel 导入向导（列映射 + 预览 + 确认）
│   ├── staff/                # 技师列表、详情（佣金历史）、表单
│   ├── courses/              # 套餐目录管理
│   ├── sessions/             # 所有上课记录、手动销课
│   ├── payments/             # 所有交易记录、待确认转账
│   ├── referrals/            # 转介绍关系图 + 奖励状态
│   ├── notifications/        # 编写并发送订阅消息 + 历史记录
│   └── export/               # 分步骤导出向导
├── components/
│   ├── CustomerSearch/       # 客户自动补全搜索组件
│   ├── StaffPicker/          # 技师选择器
│   ├── SessionDeductButton/  # 一键销课按钮
│   ├── PaymentConfirmModal/  # 确认转账弹窗
│   └── ReferralTree/         # 转介绍关系可视化
├── services/                 # Axios 实例 + 各资源 service 文件
└── utils/
    ├── import.ts             # xlsx 解析（SheetJS）
    ├── export.ts             # Excel 导出辅助
    └── format.ts             # 人民币、日期、次数格式化
```

---

## 4. 数据库设计 / Database Schema

### 设计规范

- `UUID` 主键（避免遍历攻击）
- `created_at`、`updated_at` 自动时间戳
- 软删除：`deleted_at` 可为空的时间戳列（医疗业务数据不做硬删除）
- 所有金额以**分（fen / 整数）**存储，不使用浮点数

### 实体关系图

```
User (1) ──── (0..1) StaffProfile
User (1) ──── (many) CustomerPackage     [作为客户]
User (1) ──── (many) Session             [作为客户或技师]
User (1) ──── (many) Transaction         [作为客户]
User (1) ──── (many) Referral            [作为推荐人或被推荐人]
User (1) ──── (many) NotificationLog

Course (1) ───────── (many) CustomerPackage
CustomerPackage (1) ─ (many) Session
```

---

### 表：`users` — 统一的用户表（客户 / 技师 / 管理员）

```sql
id                UUID PRIMARY KEY DEFAULT gen_random_uuid()
role              VARCHAR(20) NOT NULL DEFAULT 'customer'
                  -- 'customer'（客户）, 'therapist'（技师）, 'admin'（管理员）

-- 微信身份（首次 wx.login 时填充）
openid            VARCHAR(64) UNIQUE
unionid           VARCHAR(64) UNIQUE
wechat_nickname   VARCHAR(100)
wechat_avatar_url TEXT
wechat_phone      VARCHAR(20)       -- wx.getPhoneNumber（需用户授权）

-- 真实身份（管理员从纸质记录录入，或 Web 端注册时填写）
real_name         VARCHAR(100)
phone             VARCHAR(20)       -- Web 端登录凭据；同时作为微信账号与 Web 账号的关联键
gender            VARCHAR(10)       -- 'male', 'female', 'unknown'
date_of_birth     DATE
notes             TEXT
address           TEXT

-- 账号状态
is_active         BOOLEAN NOT NULL DEFAULT TRUE
first_login_at    TIMESTAMPTZ
last_login_at     TIMESTAMPTZ

-- Phase 2 AI 预留字段
ai_profile        JSONB DEFAULT '{}'   -- 症状档案、诊断数据

created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
deleted_at        TIMESTAMPTZ          -- 软删除
```

> **账号关联规则**: Web 端用手机号注册时，若该手机号已存在于某条微信账号记录中（`phone` 字段匹配），系统将返回同一个 `user_id`，实现一个客户、两种登录方式。

---

### 表：`staff_profiles` — 技师 / 管理员扩展信息

```sql
id                       UUID PRIMARY KEY
user_id                  UUID NOT NULL REFERENCES users(id)
specialty                VARCHAR(200)       -- 例："骶髂关节, 颈椎"
hire_date                DATE
employment_type          VARCHAR(20)        -- 'full_time', 'part_time'

-- 销售佣金（按课包成交价的百分比，以 bps 存储，2000 = 20%）
sales_commission_bps     INTEGER DEFAULT 2000

-- 技师课时佣金（两种模式二选一）
session_commission_bps   INTEGER DEFAULT 3000   -- 按课单价百分比
session_flat_rate_fen    INTEGER                 -- 或按次固定金额（分）

notes                    TEXT
created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW()
updated_at               TIMESTAMPTZ NOT NULL DEFAULT NOW()
deleted_at               TIMESTAMPTZ
```

---

### 表：`courses` — 套餐 / 课程目录

```sql
id                    UUID PRIMARY KEY
name                  VARCHAR(200) NOT NULL   -- 例："颈椎调理10次套餐"
description           TEXT
course_type           VARCHAR(50) DEFAULT 'package'
                      -- 'package'（多次套餐）, 'single'（单次）, 'trial'（体验）

session_count         INTEGER NOT NULL        -- 包含课时数
validity_days         INTEGER                 -- NULL = 不限期
price_fen             INTEGER NOT NULL        -- 标价（分）
cost_per_session_fen  INTEGER                 -- 每课时成本（分），用于报表

-- 促销定价
promo_price_fen       INTEGER
promo_start_at        TIMESTAMPTZ
promo_end_at          TIMESTAMPTZ

is_active             BOOLEAN NOT NULL DEFAULT TRUE

-- Phase 2 预留字段
sop_template_id       UUID                    -- 关联 SOP 模板（Phase 1 为 NULL）
metadata              JSONB DEFAULT '{}'

created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
deleted_at            TIMESTAMPTZ
```

---

### 表：`customer_packages` — 客户购买的课包实例

```sql
id                        UUID PRIMARY KEY
customer_id               UUID NOT NULL REFERENCES users(id)
course_id                 UUID NOT NULL REFERENCES courses(id)

purchase_date             DATE NOT NULL DEFAULT CURRENT_DATE
expiry_date               DATE                -- 由 purchase_date + validity_days 计算

-- 课时余额
sessions_total            INTEGER NOT NULL    -- 购买时从 course 复制
sessions_used             INTEGER NOT NULL DEFAULT 0
sessions_gifted           INTEGER NOT NULL DEFAULT 0   -- 来自转介绍奖励

-- 财务
agreed_price_fen          INTEGER NOT NULL    -- 实际成交价（可与标价不同）
amount_paid_fen           INTEGER NOT NULL DEFAULT 0
payment_status            VARCHAR(20) NOT NULL DEFAULT 'pending'
                          -- 'pending', 'partial', 'paid', 'refunded'

-- 销售归属
sold_by_staff_id          UUID REFERENCES users(id)
sales_commission_fen      INTEGER

-- 转介绍关联
referral_id               UUID REFERENCES referrals(id)

notes                     TEXT
created_at                TIMESTAMPTZ NOT NULL DEFAULT NOW()
updated_at                TIMESTAMPTZ NOT NULL DEFAULT NOW()
deleted_at                TIMESTAMPTZ

-- 约束：已用课时不超过总课时（含赠送）
CONSTRAINT chk_sessions_valid
    CHECK (sessions_used <= sessions_total + sessions_gifted)
```

---

### 表：`sessions` — 单次上课记录（销课）

```sql
id                        UUID PRIMARY KEY
customer_id               UUID NOT NULL REFERENCES users(id)
customer_package_id       UUID NOT NULL REFERENCES customer_packages(id)
therapist_id              UUID NOT NULL REFERENCES users(id)

scheduled_at              TIMESTAMPTZ         -- 可选，未来预约功能使用
conducted_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
duration_minutes          INTEGER DEFAULT 60

status                    VARCHAR(20) NOT NULL DEFAULT 'completed'
                          -- 'scheduled', 'completed', 'cancelled', 'no_show'

-- 治疗部位
session_type              VARCHAR(100)        -- 例："颈椎", "腰椎"
body_areas                TEXT[]              -- PostgreSQL 数组

-- 技师结算
therapist_commission_fen  INTEGER             -- 销课时计算并存储
commission_settled        BOOLEAN DEFAULT FALSE

-- 临床记录
clinical_notes            TEXT

-- Phase 2 AI 预留字段
ai_session_data           JSONB DEFAULT '{}'

created_at                TIMESTAMPTZ NOT NULL DEFAULT NOW()
updated_at                TIMESTAMPTZ NOT NULL DEFAULT NOW()
deleted_at                TIMESTAMPTZ
```

---

### 表：`transactions` — 付款记录（永久保留，不软删除）

```sql
id                        UUID PRIMARY KEY
customer_id               UUID NOT NULL REFERENCES users(id)
customer_package_id       UUID REFERENCES customer_packages(id)

amount_fen                INTEGER NOT NULL    -- 正数=收款，负数=退款
payment_method            VARCHAR(30) NOT NULL
                          -- 'wechat_pay', 'bank_transfer', 'cash', 'coupon'

-- 微信支付专属
wx_transaction_id         VARCHAR(64) UNIQUE
wx_out_trade_no           VARCHAR(64) UNIQUE  -- 我方订单号
wx_prepay_id              VARCHAR(64)

-- 银行转账专属
bank_reference            VARCHAR(100)
bank_transfer_at          DATE

status                    VARCHAR(20) NOT NULL DEFAULT 'pending'
                          -- 'pending', 'confirmed', 'failed', 'refunded'
confirmed_at              TIMESTAMPTZ
confirmed_by_id           UUID REFERENCES users(id)   -- 确认转账的管理员

-- 审计留存
raw_wx_response           JSONB               -- 完整微信支付回调内容（合规要求）
notes                     TEXT

created_at                TIMESTAMPTZ NOT NULL DEFAULT NOW()
-- 注意：财务记录永久保留，不设 deleted_at
```

---

### 表：`referrals` — 转介绍记录

```sql
id                            UUID PRIMARY KEY
referrer_id                   UUID NOT NULL REFERENCES users(id)   -- 推荐人（现有客户）
referee_id                    UUID NOT NULL REFERENCES users(id)   -- 被推荐人（新客户）

-- 触发事件：被推荐人完成首次购课时激活
triggered_by_package_id       UUID REFERENCES customer_packages(id)

-- 奖励
reward_type                   VARCHAR(30)     -- 'gift_session', 'coupon', 'cash_credit'
reward_value                  INTEGER         -- 赠送课时数 或 优惠券面额（分）
reward_status                 VARCHAR(20) DEFAULT 'pending'
                              -- 'pending', 'awarded', 'expired', 'cancelled'
reward_awarded_at             TIMESTAMPTZ
reward_applied_to_package_id  UUID REFERENCES customer_packages(id)

notes                         TEXT
created_at                    TIMESTAMPTZ NOT NULL DEFAULT NOW()
updated_at                    TIMESTAMPTZ NOT NULL DEFAULT NOW()

UNIQUE(referrer_id, referee_id)   -- 同一对关系只记录一次
```

---

### 表：`notification_logs` — 通知推送日志

```sql
id                UUID PRIMARY KEY
recipient_id      UUID NOT NULL REFERENCES users(id)

-- 微信订阅消息
template_id       VARCHAR(100) NOT NULL     -- 微信消息模板 ID
channel           VARCHAR(20) DEFAULT 'subscribe_message'
                  -- 'subscribe_message'（未来扩展：'sms', 'email', 'web_push'）

-- 内容快照
content_snapshot  JSONB NOT NULL            -- 发送时的完整消息体

-- 投递状态
status            VARCHAR(20) DEFAULT 'pending'
                  -- 'pending', 'sent', 'failed'
sent_at           TIMESTAMPTZ
wx_msg_id         VARCHAR(100)

-- 触发来源
trigger_type      VARCHAR(50)
                  -- 'manual_blast', 'session_reminder', 'package_expiry',
                  -- 'referral_reward', 'promotion'
triggered_by_id   UUID REFERENCES users(id)  -- 手动发送时的管理员

error_message     TEXT
created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
```

---

### 表：`coupons` — 优惠券（转介绍奖励等）

```sql
id                    UUID PRIMARY KEY
code                  VARCHAR(30) UNIQUE NOT NULL
customer_id           UUID REFERENCES users(id)   -- NULL = 通用券
referral_id           UUID REFERENCES referrals(id)

discount_type         VARCHAR(20) NOT NULL         -- 'fixed_fen', 'percentage_bps'
discount_value        INTEGER NOT NULL
min_purchase_fen      INTEGER DEFAULT 0
max_discount_fen      INTEGER                     -- 百分比折扣上限

valid_from            TIMESTAMPTZ
valid_until           TIMESTAMPTZ

is_used               BOOLEAN DEFAULT FALSE
used_at               TIMESTAMPTZ
used_on_package_id    UUID REFERENCES customer_packages(id)

created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
```

---

### 表：`sms_codes` — Web 端短信验证码

```sql
id            UUID PRIMARY KEY
phone         VARCHAR(20) NOT NULL
code          VARCHAR(6) NOT NULL
purpose       VARCHAR(20)              -- 'login', 'register', 'account_link'
expires_at    TIMESTAMPTZ NOT NULL
used_at       TIMESTAMPTZ
created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
```

---

## 5. 关键架构决策 / Key Architecture Decisions

### 5.1 认证流程 — 微信小程序

```
小程序: wx.login() → js_code
后端: 调用微信 jscode2session(js_code) → openid
后端: 按 openid upsert 用户，签发 JWT {user_id, role}
小程序: 将 JWT 存入 wx.storage，每次请求携带
```

- JWT：7 天有效期 + 30 天 refresh token
- 后端不存储微信 session_key

### 5.2 认证流程 — Web 端（手机号 + 短信）

```
Web: POST /api/v1/auth/request-sms {phone}
后端: 生成 6 位验证码，存入 Redis（5 分钟 TTL），通过短信发送
Web: POST /api/v1/auth/verify-sms {phone, code}
后端: 校验验证码，按 phone upsert 用户，签发 JWT {user_id, role}
Web: 将 JWT 存入 httpOnly cookie 或 localStorage
```

**账号关联**: 若短信登录的手机号与已有微信用户的 `phone` 字段一致，返回同一 `user_id`。一个客户，两种登录方式，同一条数据记录。

### 5.3 微信支付流程

**小程序（JSAPI）**:
```
POST /api/v1/payments/create-order
    → 微信支付 v3 API → 返回 prepay_id
小程序: wx.requestPayment({prepay_id, 签名参数...})
微信支付异步回调 → POST /api/v1/webhooks/wechat-pay
后端: 验签 → 标记 transaction.status='confirmed' → 更新 customer_package.payment_status
```

**Web 端（Native 扫码）**:
```
POST /api/v1/payments/create-order?channel=native
    → 微信支付 v3 API → 返回 code_url（二维码链接）
Web: 渲染二维码供用户扫描，轮询支付状态
```

银行转账：由管理员在后台手动确认（`POST /api/v1/payments/{id}/confirm`）。

### 5.4 佣金计算规则

- **销售佣金**: `agreed_price_fen × sales_commission_bps / 10000`
- **技师课时佣金**: `session_flat_rate_fen`（固定金额）或 `cost_per_session_fen × session_commission_bps / 10000`（按比例）
- 佣金在销售或销课时**即时计算并存储**，不做事后追溯修改。

### 5.5 Phase 2 预留扩展点（Phase 1 已预埋）

| 扩展点 | 位置 | 说明 |
|---|---|---|
| 客户症状档案 | `users.ai_profile JSONB` | Phase 2 存储结构化症状 / 诊断数据 |
| 单次课 AI 评估 | `sessions.ai_session_data JSONB` | Phase 2 存储 AI 诊断输出 |
| SOP 模板绑定 | `courses.sop_template_id UUID` | Phase 1 为 NULL；Phase 2 创建 `sop_templates` 表后关联 |
| AI API 命名空间 | `/api/v2/` | 为 Phase 2 AI 接口预留路由前缀 |
| 多渠道通知 | `notification_logs.channel` | 支持未来扩展 `sms`、`email`、`web_push` |
| Web 端目录 | `webapp/` | Phase 1 创建空 Next.js 项目骨架，Phase 2 开始填充 |

---

## 6. 管理后台用户体验原则 / Admin Panel UX for Non-Technical Owner

1. **仪表盘优先**: 首页一览：今日上课场次、活跃客户数、待收款金额、本月营收
2. **一键销课**: 每位客户详情页顶部放置醒目的「记录上课」按钮 → 选技师 → 一键完成
3. **引导式表单**: 每个输入项配有中文帮助说明
4. **Excel 导入向导**: 上传 → 自动识别列 → 字段映射预览 → 确认导入
5. **导出向导**: 筛选条件 → 勾选字段 → 下载 Excel
6. **订阅消息编辑器**: 选模板 → 填写内容 → "发送给所有活跃客户" 一键开关

---

## 7. 验收测试清单 / End-to-End Verification Checklist

| # | 测试场景 | 预期结果 |
|---|---|---|
| 1 | 微信开发者工具模拟登录 | `openid` 写入 DB，返回有效 JWT |
| 2 | Web 端手机号 + 短信验证码登录 | 发送验证码 → 校验 → 返回 JWT |
| 3 | 同一手机号双端关联 | 微信和 Web 登录返回相同 `user_id` |
| 4 | 上传 5 行 Excel 导入客户 | 列映射 UI 展示 → 确认后客户数据写入 DB |
| 5 | 管理后台手动新增客户 | 表单提交 → 客户出现在列表中 |
| 6 | 销课操作 | `sessions_used` +1，`therapist_commission_fen` 正确计算 |
| 7 | 微信支付沙箱测试 | 下单 → 模拟回调 → `transaction.status='confirmed'`，课包标记已付款 |
| 8 | 导出 Excel | 筛选 → 下载 → 所有字段完整 |
| 9 | 订阅消息推送 | 用户授权 → 管理后台触发 → `notification_logs` 有记录 |
| 10 | 转介绍奖励 | 新客户购课 → `reward_status='awarded'`，推荐人 `sessions_gifted` +N |

---

## 8. 技术选型决策记录 / Architecture Decision Log

| 决策 | 选择 | 被放弃的方案 | 理由 |
|---|---|---|---|
| 小程序框架 | Taro 4 + React | 原生 WXML | TypeScript 支持、React 开发体验、未来可扩展 H5 |
| Web 端框架 | Next.js 14 | Taro H5 编译 | Taro H5 产物为移动优先 UI；Next.js 提供真正的 Web 体验和 SSR |
| 后端语言 | Python + FastAPI | Node.js + NestJS | Phase 2 AI/ML 集成；Python 生态优势明显 |
| 数据库 | PostgreSQL | MySQL | JSONB 支持 AI 预留字段；TEXT[] 原生数组；更强的约束能力 |
| 云服务商 | 腾讯云 | 阿里云、AWS | 微信支付/开放平台回调延迟最低；ICP 备案更顺畅 |
| 管理后台 | Ant Design Pro | 自建 UI | 国内企业管理系统事实标准；ProTable/ProForm 大幅减少 CRUD 代码量 |
| 部署方式 | Docker Compose | Kubernetes | 单人维护、Phase 1 规模不需要 K8s 复杂度 |

---

*文档结束 / End of Document*
