# 系统架构设计文档
# Physical Therapy Store App — System Architecture Design

> **版本 / Version**: 1.0 | **日期 / Date**: 2026-02-28
> **关联文档**: 门店app开发需求.docx | tech-stack.md

---

## 目录 / Table of Contents

1. [系统架构图](#1-系统架构图)
2. [数据库实体关系图 (ERD)](#2-数据库实体关系图-erd)
3. [API 接口规范](#3-api-接口规范)
4. [状态机逻辑](#4-状态机逻辑)
5. [技术选型理由](#5-技术选型理由)
6. [微信小程序配置与部署](#6-微信小程序配置与部署)
7. [Git 操作指南](#7-git-操作指南)
8. [并发控制、排班冲突与账号打通](#8-并发控制排班冲突与账号打通)

---

## 1. 系统架构图

### 1.1 整体分层架构

```
┌──────────────────────────────────────────────────────────────────┐
│                        客户端层 CLIENT LAYER                      │
│                                                                    │
│  ┌─────────────────────┐  ┌──────────────────┐  ┌─────────────┐  │
│  │  微信小程序           │  │   Web 网页端       │  │  管理后台    │  │
│  │  WeChat Mini-App     │  │  (Phase 2)        │  │  Admin Panel│  │
│  │  Taro 4 + React      │  │  Next.js 14       │  │  Ant Design │  │
│  │  TypeScript          │  │  App Router       │  │  Pro 5      │  │
│  │  ● Phase 1 核心       │  │  ● Phase 2 扩展    │  │  ● Phase 1  │  │
│  └──────────┬───────────┘  └────────┬─────────┘  └──────┬──────┘  │
└─────────────┼────────────────────────┼───────────────────┼─────────┘
              │ HTTPS                  │ HTTPS             │ HTTPS
              │ wx.request()           │ fetch/axios       │ axios
              └──────────────┬─────────┘                   │
                             │                             │
┌────────────────────────────┼─────────────────────────────┼────────┐
│                   网关层 API GATEWAY                               │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │                        Nginx                                │   │
│  │  /api/*  ────────────► FastAPI :8000                        │   │
│  │  /admin/* ───────────► Static Files (Admin Panel Build)     │   │
│  │  /webhooks/* ────────► FastAPI :8000 (WeChat callbacks)     │   │
│  │  TLS 终止 / 负载均衡 / 限流                                    │   │
│  └────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────┘
                             │
┌────────────────────────────┼─────────────────────────────────────┐
│                    后端层 BACKEND LAYER                            │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐   │
│  │          FastAPI Application (Python 3.12)                 │   │
│  │                                                            │   │
│  │  routers/          core/              models/              │   │
│  │  ├── auth          ├── wechat.py      ├── user             │   │
│  │  ├── customers     │   (WeChatPy)     ├── staff_profile    │   │
│  │  ├── staff         ├── security.py   ├── course            │   │
│  │  ├── courses       │   (JWT)          ├── customer_package  │   │
│  │  ├── packages      └── exceptions    ├── session           │   │
│  │  ├── sessions                         ├── transaction       │   │
│  │  ├── payments      deps.py            ├── referral         │   │
│  │  ├── referrals     (DB Session,       ├── notification_log  │   │
│  │  ├── notifications  current_user)     ├── coupon           │   │
│  │  └── export                           └── sms_code         │   │
│  └───────────────────────────────────────────────────────────┘   │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐   │
│  │               Celery Worker (Async Tasks)                  │   │
│  │  tasks.py                                                  │   │
│  │  ├── send_blast_notification()   批量订阅消息发送             │   │
│  │  ├── check_referral_expiry()     转介绍到期检查 (每日)        │   │
│  │  └── generate_excel_export()     大体量 Excel 导出           │   │
│  └───────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────┘
                             │
┌────────────────────────────┼─────────────────────────────────────┐
│                    数据层 DATA LAYER                               │
│                                                                   │
│  ┌──────────────────────┐    ┌──────────────────────────────┐    │
│  │    PostgreSQL 15      │    │         Redis 7              │    │
│  │    (TencentDB)        │    │    (Tencent Cloud Redis)     │    │
│  │                       │    │                              │    │
│  │  ● users              │    │  ● WeChat access_token 缓存  │    │
│  │  ● staff_profiles     │    │    (微信限频: 每日2000次)      │    │
│  │  ● courses            │    │  ● JWT 黑名单 (logout)        │    │
│  │  ● customer_packages  │    │  ● SMS 验证码 (5分钟TTL)      │    │
│  │  ● sessions           │    │  ● Celery 任务队列            │    │
│  │  ● transactions       │    │  ● API 限流计数器             │    │
│  │  ● referrals          │    │                              │    │
│  │  ● notification_logs  │    └──────────────────────────────┘    │
│  │  ● coupons            │                                        │
│  │  ● sms_codes          │    ┌──────────────────────────────┐    │
│  └──────────────────────┘    │    腾讯云 COS                 │    │
│                               │  ● 客户头像 / 上传文件        │    │
│                               │  ● 导出的 Excel 文件          │    │
│                               └──────────────────────────────┘    │
└────────────────────────────────────────────────────────────────────┘
                             │
┌────────────────────────────┼─────────────────────────────────────┐
│               外部接口层 EXTERNAL SERVICES                         │
│                                                                   │
│  ┌──────────────────────┐    ┌──────────────────────────────┐    │
│  │  微信开放平台          │    │   AI Agent (Phase 2 预留)    │    │
│  │  WeChat Open Platform│    │                              │    │
│  │                       │    │  ● /api/v2/ai/diagnose       │    │
│  │  ● wx.login           │    │    症状诊断接口               │    │
│  │    jscode2session     │    │  ● /api/v2/ai/recommend-sop  │    │
│  │  ● 订阅消息            │    │    SOP 推荐接口               │    │
│  │    Subscribe Messages │    │  ● 可接 LangChain/OpenAI     │    │
│  │  ● 微信支付 v3         │    │    或本地模型                 │    │
│  │    JSAPI / Native QR  │    │                              │    │
│  │  ● 微信网页授权        │    └──────────────────────────────┘    │
│  │    (Phase 2 Web)      │                                        │
│  └──────────────────────┘    ┌──────────────────────────────┐    │
│                               │  腾讯云短信 SMS (Phase 2)    │    │
│                               │  ● Web 端登录验证码           │    │
│                               └──────────────────────────────┘    │
└────────────────────────────────────────────────────────────────────┘
```

### 1.2 核心数据流说明

**Phase 1 核心战略目标**: 将客户资产的掌控权从各技师手中转移到门店系统。技师对"自己客户"的独占式掌控（客户信息、课时记录均在技师私人手机/笔记）将被打破——所有数据统一沉淀到后台，店长可随时查看任意客户的全貌，为未来团队协作服务（Phase 2）打好数据基础。

| 场景 | 数据流路径 |
|---|---|
| **[Phase 1 核心] 手动录入客户数据** | 店长/技师在管理后台 → 手动新增客户档案 + 补录历史课包/付款记录 → PostgreSQL → 客户资产从技师私有转为门店所有 |
| **[Phase 1 核心] 批量导入历史数据** | 店长整理 Excel → POST /api/v1/customers/import → 系统自动匹配/新建客户 → 返回导入报告 |
| 客户微信登录 | 小程序 → wx.login() → 后端 → 微信 jscode2session → 生成 JWT → 返回小程序 |
| 客户预约 | 小程序 → POST /api/v1/sessions → FastAPI → PostgreSQL → 返回预约单 |
| 管理员确认预约 | 管理后台 → PATCH /api/v1/sessions/{id}/confirm → FastAPI → PostgreSQL |
| 管理员销课 | 管理后台 → PATCH /api/v1/sessions/{id}/complete → FastAPI → 扣课时+计佣金 → PostgreSQL |
| 微信支付 | 小程序 → POST /api/v1/payments/wechat/create-order → 微信支付 API → 返回 prepay_id → 小程序 wx.requestPayment() → 微信异步回调 → /webhooks/wechat-pay → 确认付款 |
| 批量推送通知 | 管理后台 → POST /api/v1/notifications/blast → Celery 异步任务 → 微信订阅消息 API |
| 转介绍奖励 | 被推荐人首次付款完成 → /webhooks/wechat-pay 确认 → 系统检查 referral → 自动加赠课时 |

---

## 2. 数据库实体关系图 (ERD)

### 2.1 关系概览

```
users (1) ─────────── (0..1) staff_profiles
                              [一个用户最多有一个技师档案]

users (1) ─────────── (0..N) customer_packages
                              [一个客户可以购买多个课包]

courses (1) ─────────── (0..N) customer_packages
                               [一个课程可被多个客户购买]

customer_packages (1) ─── (0..N) sessions
                                 [一个课包可以消耗多次课时]

users/customer (1) ─── (0..N) sessions [作为客户]
users/therapist (1) ─── (0..N) sessions [作为技师]
                                [技师可以服务不同客户，客户可以选不同技师]

customer_packages (1) ─── (0..N) transactions
                                  [一个课包可以有多笔付款记录]

users (1) ─── (0..N) referrals [作为推荐人 referrer]
users (1) ─── (0..1) referrals [作为被推荐人 referee，只能被推荐一次]

referrals (1) ─── (0..1) coupons [一条转介绍可奖励一张优惠券]

users (1) ─── (0..N) notification_logs

staff_profiles (1) ─── (0..N) therapist_availability
                               [技师每日可服务时段配置，预约创建时用于冲突检测]
```

### 2.2 ERD 图示

```
┌──────────────────────────────────────────────────────────────┐
│                         users                                │
├──────────────────────────────────────────────────────────────┤
│ PK  id               UUID                                    │
│     role             VARCHAR(20)   customer/therapist/admin   │
│     openid           VARCHAR(64)   UNIQUE (微信身份)           │
│     unionid          VARCHAR(64)   UNIQUE                    │
│     wechat_nickname  VARCHAR(100)                            │
│     wechat_avatar    TEXT                                    │
│     wechat_phone     VARCHAR(20)   (wx.getPhoneNumber)       │
│     real_name        VARCHAR(100)                            │
│     phone            VARCHAR(20)   UNIQUE (Web 登录凭据)       │
│     gender           VARCHAR(10)   male/female/unknown       │
│     date_of_birth    DATE                                    │
│     notes            TEXT                                    │
│     address          TEXT                                    │
│     is_active        BOOLEAN       DEFAULT TRUE              │
│     ai_profile       JSONB         {} (Phase 2 预留)          │
│     first_login_at   TIMESTAMPTZ                             │
│     last_login_at    TIMESTAMPTZ                             │
│     created_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW()    │
│     updated_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW()    │
│     deleted_at       TIMESTAMPTZ   软删除                     │
└───────────────┬──────────────────────────────────────────────┘
                │ 1:0..1
                ▼
┌──────────────────────────────────────────────────────────────┐
│                     staff_profiles                           │
├──────────────────────────────────────────────────────────────┤
│ PK  id                    UUID                               │
│ FK  user_id               UUID  → users.id                  │
│     specialty             VARCHAR(200)  "骶髂关节, 颈椎"       │
│     hire_date             DATE                               │
│     employment_type       VARCHAR(20)   full_time/part_time  │
│     sales_commission_bps  INTEGER       2000 = 20%           │
│     session_commission_bps INTEGER      3000 = 30%           │
│     session_flat_rate_fen  INTEGER      或固定金额(分)         │
│     notes                 TEXT                               │
│     created_at            TIMESTAMPTZ                        │
│     updated_at            TIMESTAMPTZ                        │
│     deleted_at            TIMESTAMPTZ                        │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│       therapist_availability   (Phase 2 预留，Phase 1 不启用)  │
├──────────────────────────────────────────────────────────────┤
│ PK  id            UUID                                       │
│ FK  staff_id      UUID  → users.id                           │
│     date          DATE   NOT NULL  (当日日期 yyyy-mm-dd)       │
│     start_time    TIME   NOT NULL  (可服务开始，如 09:00)      │
│     end_time      TIME   NOT NULL  (可服务结束，如 18:00)      │
│     is_available  BOOLEAN  DEFAULT TRUE  (FALSE=请假/休息)    │
│     notes         TEXT                                       │
│     created_at    TIMESTAMPTZ                                │
│     updated_at    TIMESTAMPTZ                                │
│                                                              │
│  ● UNIQUE(staff_id, date, start_time)                        │
│  ● Phase 1 不启用：售课即服务，无需跨技师排班管理               │
│  ● Phase 2 启用：多技师治疗方案模式下，创建 Session 前须查此表  │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│                        courses                               │
├──────────────────────────────────────────────────────────────┤
│ PK  id                UUID                                   │
│     name              VARCHAR(200)  "肩颈调理套餐 10次"        │
│     description       TEXT                                   │
│     course_type       VARCHAR(50)   package/single/trial     │
│     session_count     INTEGER       NOT NULL                 │
│     validity_days     INTEGER       NULL = 不限期             │
│     price_fen         INTEGER       NOT NULL (分, 整数)       │
│     cost_per_session_fen INTEGER    price / session_count    │
│     promo_price_fen   INTEGER       NULL = 无促销             │
│     promo_start_at    TIMESTAMPTZ                            │
│     promo_end_at      TIMESTAMPTZ                            │
│     is_active         BOOLEAN       DEFAULT TRUE             │
│     sop_template_id   UUID          NULL (Phase 2 预留)       │
│     metadata          JSONB         {}                       │
│     created_at        TIMESTAMPTZ                            │
│     updated_at        TIMESTAMPTZ                            │
│     deleted_at        TIMESTAMPTZ                            │
└───────────────┬──────────────────────────────────────────────┘
                │ 1:N
                ▼
┌──────────────────────────────────────────────────────────────┐
│                   customer_packages                          │
├──────────────────────────────────────────────────────────────┤
│ PK  id                    UUID                               │
│ FK  customer_id           UUID  → users.id                  │
│ FK  course_id             UUID  → courses.id                │
│ FK  sold_by_staff_id      UUID  → users.id  (nullable)      │
│ FK  referral_id           UUID  → referrals.id  (nullable)  │
│     purchase_date         DATE  DEFAULT CURRENT_DATE         │
│     expiry_date           DATE  (由 validity_days 计算)       │
│     sessions_total        INTEGER  NOT NULL                  │
│     sessions_used         INTEGER  DEFAULT 0                 │
│     sessions_gifted       INTEGER  DEFAULT 0  (转介绍赠送)    │
│     agreed_price_fen      INTEGER  NOT NULL  (实际成交价)      │
│     amount_paid_fen       INTEGER  DEFAULT 0                 │
│     payment_status        VARCHAR(20)                        │
│         pending / partial / paid / refunded                  │
│     sold_by_commission_fen INTEGER  (销售佣金, 分)            │
│     notes                 TEXT                               │
│     created_at            TIMESTAMPTZ                        │
│     updated_at            TIMESTAMPTZ                        │
│     deleted_at            TIMESTAMPTZ                        │
│                                                              │
│  ● CONSTRAINT: sessions_used <= sessions_total+sessions_gifted│
│  ● INDEX: customer_id, payment_status, expiry_date           │
└───────────────┬──────────────────────────────────────────────┘
                │ 1:N
                ▼
┌──────────────────────────────────────────────────────────────┐
│                       sessions                               │
├──────────────────────────────────────────────────────────────┤
│ PK  id                      UUID                             │
│ FK  customer_id             UUID  → users.id                │
│ FK  customer_package_id     UUID  → customer_packages.id    │
│ FK  therapist_id            UUID  → users.id                │
│                             Phase 1: 须等于                  │
│                             customer_packages.sold_by_staff_id│
│                             Phase 2: 可由治疗方案独立指定技师  │
│     scheduled_at            TIMESTAMPTZ  (客户预约的时间)      │
│     confirmed_at            TIMESTAMPTZ  (管理员确认时间)      │
│     completed_at            TIMESTAMPTZ  (实际完成时间)        │
│     duration_minutes        INTEGER  DEFAULT 60              │
│     status                  VARCHAR(20)                      │
│         pending/confirmed/completed/cancelled/no_show        │
│     session_type            VARCHAR(100)  "颈椎", "腰椎"     │
│     body_areas              TEXT[]  PostgreSQL 数组           │
│     therapist_commission_fen INTEGER  (完成时计算)             │
│     commission_settled      BOOLEAN  DEFAULT FALSE           │
│     clinical_notes          TEXT                             │
│     cancel_reason           TEXT  (取消原因)                  │
│     ai_session_data         JSONB  {} (Phase 2 预留)          │
│     created_at              TIMESTAMPTZ                      │
│     updated_at              TIMESTAMPTZ                      │
│     deleted_at              TIMESTAMPTZ                      │
│                                                              │
│  ● INDEX: customer_id, therapist_id, scheduled_at, status   │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│                     transactions                             │
├──────────────────────────────────────────────────────────────┤
│ PK  id                    UUID                               │
│ FK  customer_id           UUID  → users.id                  │
│ FK  customer_package_id   UUID  → customer_packages.id      │
│ FK  confirmed_by_id       UUID  → users.id  (nullable)      │
│     amount_fen            INTEGER  (正数=收款, 负数=退款)      │
│     payment_method        VARCHAR(30)                        │
│         wechat_pay / bank_transfer / cash / coupon           │
│     wx_transaction_id     VARCHAR(64)  UNIQUE                │
│     wx_out_trade_no       VARCHAR(64)  UNIQUE  (我方订单号)   │
│     wx_prepay_id          VARCHAR(64)                        │
│     bank_reference        VARCHAR(100)                       │
│     bank_transfer_at      DATE                               │
│     status                VARCHAR(20)                        │
│         pending / confirmed / failed / cancelled             │
│     confirmed_at          TIMESTAMPTZ                        │
│     raw_wx_response       JSONB  (完整回调, 合规存档)          │
│     notes                 TEXT                               │
│     created_at            TIMESTAMPTZ                        │
│  ● 永久保留，无 deleted_at                                    │
│  ● INDEX: customer_id, status, wx_transaction_id             │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│                       referrals                              │
├──────────────────────────────────────────────────────────────┤
│ PK  id                             UUID                      │
│ FK  referrer_id                    UUID  → users.id         │
│ FK  referee_id                     UUID  → users.id         │
│ FK  triggered_by_package_id        UUID  → customer_packages│
│ FK  reward_applied_to_package_id   UUID  → customer_packages│
│     reward_type     VARCHAR(30)  gift_session/coupon/cash    │
│     reward_value    INTEGER      (课时数 或 优惠券面额/分)     │
│     reward_status   VARCHAR(20)  pending/awarded/expired/    │
│                                  cancelled                   │
│     reward_awarded_at TIMESTAMPTZ                            │
│     expiry_date       DATE       (到期未购课则变 expired)      │
│     notes             TEXT                                   │
│     created_at        TIMESTAMPTZ                            │
│     updated_at        TIMESTAMPTZ                            │
│  ● UNIQUE(referrer_id, referee_id)                           │
└───────────────┬──────────────────────────────────────────────┘
                │ 1:0..1
                ▼
┌──────────────────────────────────────────────────────────────┐
│                        coupons                               │
├──────────────────────────────────────────────────────────────┤
│ PK  id                  UUID                                 │
│     code                VARCHAR(30)  UNIQUE  (如 REF-ABCD)   │
│ FK  customer_id         UUID  → users.id  (NULL=通用券)      │
│ FK  referral_id         UUID  → referrals.id                │
│     discount_type       VARCHAR(20)  fixed_fen/percentage_bps│
│     discount_value      INTEGER                              │
│     min_purchase_fen    INTEGER  DEFAULT 0                   │
│     valid_from          TIMESTAMPTZ                          │
│     valid_until         TIMESTAMPTZ                          │
│     is_used             BOOLEAN  DEFAULT FALSE               │
│     used_at             TIMESTAMPTZ                          │
│ FK  used_on_package_id  UUID  → customer_packages.id        │
│     created_at          TIMESTAMPTZ                          │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│                   notification_logs                          │
├──────────────────────────────────────────────────────────────┤
│ PK  id               UUID                                    │
│ FK  recipient_id     UUID  → users.id                       │
│ FK  triggered_by_id  UUID  → users.id  (管理员, nullable)    │
│     template_id      VARCHAR(100)  微信消息模板ID             │
│     channel          VARCHAR(20)   subscribe_message         │
│                       (未来扩展: sms/email/web_push)          │
│     content_snapshot JSONB  NOT NULL  (发送时的完整消息体)     │
│     status           VARCHAR(20)  pending/sent/failed        │
│     sent_at          TIMESTAMPTZ                             │
│     wx_msg_id        VARCHAR(100)                            │
│     trigger_type     VARCHAR(50)                             │
│         manual_blast / session_reminder / package_expiry /   │
│         referral_reward / promotion                          │
│     error_message    TEXT                                    │
│     created_at       TIMESTAMPTZ                             │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│                       sms_codes                              │
│                      (Phase 2 Web 端登录)                     │
├──────────────────────────────────────────────────────────────┤
│ PK  id          UUID                                         │
│     phone       VARCHAR(20)  NOT NULL                        │
│     code        VARCHAR(6)   NOT NULL  (6位数字)              │
│     purpose     VARCHAR(20)  login/register/account_link     │
│     expires_at  TIMESTAMPTZ  NOT NULL  (5分钟TTL)            │
│     used_at     TIMESTAMPTZ  NULL = 未使用                    │
│     created_at  TIMESTAMPTZ                                  │
└──────────────────────────────────────────────────────────────┘
```

### 2.3 关键业务规则（体现在数据库约束中）

| 规则 | 实现方式 |
|---|---|
| 已用课时不超过总课时（含赠送） | `CHECK (sessions_used <= sessions_total + sessions_gifted)` |
| 同一对推荐关系唯一 | `UNIQUE(referrer_id, referee_id)` |
| 微信 openid 全局唯一 | `UNIQUE INDEX ON users(openid)` |
| 手机号全局唯一 | `UNIQUE INDEX ON users(phone)` |
| 财务记录永久保留 | `transactions` 表无 `deleted_at` 列 |
| 金额统一用分存储 | 所有 `_fen` 字段为 `INTEGER`，避免浮点精度问题 |
| **Phase 1** 售课即服务 | 创建 Session 时后端须校验 `sessions.therapist_id = customer_packages.sold_by_staff_id`；违反则返回 400，确保 Phase 1 内每位客户始终由其签约技师服务 |
| **Phase 2** 技师排班冲突检测 | 启用多技师治疗方案后，创建 Session 时后端查询 `therapist_availability` 及同时段 `sessions`（status IN pending/confirmed），若冲突返回 409；此表 Phase 1 建库但不启用 |
| UnionID 跨平台账号合并 | `users.unionid` 为微信开放平台统一标识；PC Web 微信登录时须优先以 `unionid` 查找已有账号合并，禁止创建重复用户；小程序须绑定微信开放平台主体才能获取 `unionid` |
| 销课并发行锁 | `PATCH /sessions/{id}/complete` 须先 `SELECT ... FOR UPDATE` 锁定 `sessions` 行做幂等检查，再锁定 `customer_packages` 行执行 `sessions_used += 1`，全程在同一数据库事务内完成，防止并发双重销课 |

---

## 3. API 接口规范

### 3.1 基础信息

```
生产环境: https://api.yourdomain.com/api/v1
测试环境: https://staging.yourdomain.com/api/v1
本地开发: http://localhost:8000/api/v1
```

**所有认证接口需携带 Header**:
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

### 3.2 JWT Token 结构

**Access Token Payload**:
```json
{
  "sub": "usr_01J9XZ2M3N4K5P6Q7R8S9T0V",
  "role": "customer",
  "phone": "13800138000",
  "wx_openid": "oXXXXXXXXXXXXXXXXXXXXXXXX",
  "wx_unionid": "oYYYYYYYYYYYYYYYYYYYYYYYY",
  "staff_id": null,
  "iat": 1740700800,
  "exp": 1740787200
}
```

| 字段 | 说明 |
|---|---|
| `sub` | 用户 UUID |
| `role` | `admin` / `staff` / `customer` |
| `phone` | 绑定手机号（可为 null） |
| `wx_openid` | 微信 openid（可为 null） |
| `wx_unionid` | 微信开放平台 UnionID（跨端账号合并必填，可为 null） |
| `staff_id` | 技师档案 ID（仅 role=staff 时有值） |

**Token 有效期**: Access Token 24小时；Refresh Token 7天

### 3.3 标准响应格式

**成功 — 单条资源**:
```json
{
  "success": true,
  "data": { "id": "...", "name": "..." },
  "meta": null
}
```

**成功 — 分页列表**:
```json
{
  "success": true,
  "data": [ { "id": "..." } ],
  "meta": {
    "page": 1,
    "page_size": 20,
    "total_items": 143,
    "total_pages": 8,
    "has_next": true,
    "has_prev": false
  }
}
```

**错误**:
```json
{
  "success": false,
  "error": {
    "code": "PACKAGE_INSUFFICIENT_SESSIONS",
    "message": "该课包已无剩余课时。",
    "details": { "package_id": "cpkg_...", "remaining": 0 }
  }
}
```

### 3.4 通用分页参数

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `page` | int | 1 | 页码（从1开始） |
| `page_size` | int | 20 | 每页条数，最大100 |
| `sort_by` | string | varies | 排序字段名 |
| `sort_order` | string | `desc` | `asc` 或 `desc` |

### 3.5 HTTP 状态码说明

| 状态码 | 含义 |
|---|---|
| 200 | 请求成功 |
| 201 | 资源创建成功 |
| 204 | 成功但无响应体 |
| 400 | 业务规则违反（如课时不足） |
| 401 | Token 缺失、无效或过期 |
| 403 | 权限不足 |
| 404 | 资源不存在 |
| 409 | 冲突（如手机号重复） |
| 422 | 请求体字段校验失败 |
| 429 | 请求频率超限 |
| 503 | 外部服务不可用（如微信API） |

### 3.6 接口列表

#### 认证 Auth

| 方法 | 路径 | 调用方 | 说明 |
|---|---|---|---|
| POST | `/auth/wx-login` | 小程序 | 微信 code 换 JWT |
| POST | `/auth/admin-login` | 管理后台 | 手机号+密码登录 |
| POST | `/auth/token/refresh` | 所有客户端 | 刷新 Access Token |
| POST | `/auth/logout` | 所有客户端 | 吊销 Token |
| POST | `/auth/sms/send-otp` | Web 端 (Phase 2) | 发送短信验证码 |
| POST | `/auth/sms/verify-otp` | Web 端 (Phase 2) | 验证短信验证码换 JWT |

**POST /auth/wx-login — 请求示例**:
```json
{
  "code": "wx_auth_code_from_wx.login_api",
  "nickname": "张三",
  "avatar_url": "https://thirdwx.qlogo.cn/mmopen/abc123/132",
  "referral_code": "REF-ABCD"
}
```

**POST /auth/wx-login — 响应示例**:
```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGci...",
    "refresh_token": "eyJhbGci...",
    "token_type": "Bearer",
    "expires_in": 86400,
    "user": {
      "id": "usr_01J9...",
      "role": "customer",
      "nickname": "张三",
      "phone": null,
      "is_new_user": true
    }
  },
  "meta": null
}
```

#### 客户 Customers

| 方法 | 路径 | 调用方 | 说明 |
|---|---|---|---|
| GET | `/customers` | admin | 列表（支持搜索/筛选/分页） |
| POST | `/customers` | admin | 手动新增客户 |
| GET | `/customers/me` | customer | 当前用户自己的档案 |
| GET | `/customers/{id}` | admin / self | 客户详情（含课包列表） |
| PATCH | `/customers/{id}` | admin / self（受限字段） | 更新档案 |
| DELETE | `/customers/{id}` | admin | 软删除 |
| POST | `/customers/import` | admin | Excel 批量导入（最多500行） |

**POST /customers/import — 响应示例**:
```json
{
  "success": true,
  "data": {
    "total_rows": 120, "created": 105, "updated": 8, "skipped": 4,
    "errors": [
      { "row": 23, "phone": "invalid", "reason": "手机号格式无效" }
    ]
  }
}
```

#### 技师 Staff

| 方法 | 路径 | 调用方 | 说明 |
|---|---|---|---|
| GET | `/staff` | admin | 技师列表 |
| POST | `/staff` | admin | 新增技师账号 |
| GET | `/staff/{id}` | admin / self | 技师详情 |
| PATCH | `/staff/{id}` | admin | 更新技师信息 |
| DELETE | `/staff/{id}` | admin | 软删除技师 |
| GET | `/staff/{id}/commission-summary` | admin / self | 指定时间段佣金汇总 |
| GET | `/staff/{id}/availability` | admin / self | 查询技师某周期排班 |
| POST | `/staff/{id}/availability` | admin | 新增/批量设置技师可服务时段 |
| DELETE | `/staff/{id}/availability/{date}` | admin | 删除某日排班（标记休息/请假） |

#### 课程目录 Courses

| 方法 | 路径 | 调用方 | 说明 |
|---|---|---|---|
| GET | `/courses` | 所有认证用户 | 课程列表（客户只看 active） |
| POST | `/courses` | admin | 新增课程 |
| GET | `/courses/{id}` | 所有认证用户 | 课程详情 |
| PATCH | `/courses/{id}` | admin | 更新课程 |
| DELETE | `/courses/{id}` | admin | 下架课程（有活跃课包时拒绝） |
| GET | `/packages` | 所有认证用户 | 课包套餐列表 |
| POST | `/packages` | admin | 新增套餐模板 |
| PATCH | `/packages/{id}` | admin | 更新套餐 |
| DELETE | `/packages/{id}` | admin | 下架套餐 |

#### 客户课包 Customer Packages

| 方法 | 路径 | 调用方 | 说明 |
|---|---|---|---|
| GET | `/customer-packages` | admin | 全部购买记录（可筛选） |
| POST | `/customer-packages` | admin / customer | 创建购买记录（支付前） |
| GET | `/customer-packages/{id}` | admin / owner | 课包详情（含上课历史） |
| GET | `/customers/{id}/packages` | admin / self | 某客户的全部课包 |
| PATCH | `/customer-packages/{id}` | admin | 确认付款/更新备注 |
| DELETE | `/customer-packages/{id}` | admin | 取消课包 |

#### 预约与销课 Sessions

| 方法 | 路径 | 调用方 | 说明 |
|---|---|---|---|
| POST | `/sessions` | customer / admin | 发起预约（状态: pending）；后端自动检测技师时段冲突，冲突返回 409 |
| GET | `/sessions` | admin(全部) / customer(自己) | 预约/销课列表 |
| GET | `/sessions/{id}` | admin / participant | 预约详情 |
| PATCH | `/sessions/{id}/confirm` | admin | 确认预约（pending→confirmed） |
| PATCH | `/sessions/{id}/complete` | admin | 销课完成（触发扣课时+计佣金） |
| PATCH | `/sessions/{id}/cancel` | admin / customer | 取消预约（→cancelled） |
| PATCH | `/sessions/{id}/no-show` | admin | 标记未到场（→no_show，不扣课时） |

**POST /sessions — 请求示例**:
```json
{
  "customer_package_id": "cpkg_01J9...",
  "staff_id": "stf_01J9...",
  "scheduled_at": "2026-03-05T14:00:00+08:00",
  "notes": "请准备热敷垫"
}
```

**PATCH /sessions/{id}/complete — 请求示例** (触发扣课时+佣金计算):
```json
{
  "actual_duration_minutes": 65,
  "session_type": "颈椎",
  "body_areas": ["颈椎", "肩部"],
  "clinical_notes": "客户反映左侧肩部紧张，已重点处理。"
}
```

#### 支付 Payments

| 方法 | 路径 | 调用方 | 说明 |
|---|---|---|---|
| POST | `/payments/wechat/create-order` | customer / admin | 创建微信支付订单，返回 prepay_id |
| GET | `/payments/wechat/order-status/{tx_id}` | customer | 查询支付状态（前端轮询） |
| POST | `/payments` | admin | 手动录入付款（现金/转账） |
| GET | `/payments` | admin | 全部交易记录 |
| GET | `/payments/pending-transfers` | admin | 待确认银行转账列表 |
| POST | `/webhooks/wechat-pay` | 微信服务器（无需 Auth） | 支付异步回调（自动验签） |

**微信支付回调处理逻辑**（后端自动执行，前端无需调用）:
1. 验证微信签名
2. 解密通知 body
3. 更新 `transaction.status = 'confirmed'`
4. 更新 `customer_package.payment_status = 'paid'`
5. 检查转介绍奖励：若是首次付款且有关联 referral → `reward_status = 'awarded'`，给推荐人加 `sessions_gifted`
6. 返回 `{ "code": "SUCCESS", "message": "成功" }`

#### 转介绍 Referrals

| 方法 | 路径 | 调用方 | 说明 |
|---|---|---|---|
| GET | `/referrals/my-code` | customer | 获取自己的转介绍码和统计 |
| GET | `/referrals` | admin | 全部转介绍记录 |
| PATCH | `/referrals/{id}/cancel` | admin | 手动取消转介绍 |

#### 通知 Notifications

| 方法 | 路径 | 调用方 | 说明 |
|---|---|---|---|
| POST | `/notifications/blast` | admin | 发送群发订阅消息（Celery 异步） |
| GET | `/notifications/blast/{job_id}` | admin | 查询群发任务状态 |
| GET | `/notifications/logs` | admin | 通知发送日志 |

#### 导出 Export

| 方法 | 路径 | 调用方 | 说明 |
|---|---|---|---|
| GET | `/export/customers` | admin | 导出客户列表 Excel |
| GET | `/export/sessions` | admin | 导出上课记录 Excel |
| GET | `/export/commissions` | admin | 导出技师佣金汇总 Excel |

---

## 4. 状态机逻辑

### 4.1 预约/销课状态机 (Session State Machine)

```
                    ┌─────────────────────────┐
                    │   客户在小程序填写预约     │
                    │   (选日期/时间/技师/课包)  │
                    └────────────┬────────────┘
                                 │ POST /sessions
                                 ▼
                    ┌────────────────────────────────────┐
                    │  后端校验（Phase 1 必须）            │
                    │  therapist_id ==                   │
                    │  customer_package.sold_by_staff_id?│
                    └──────┬──────────────┬─────────────┘
              校验通过       │              │  不一致
                            ▼              ▼
                                  ┌─────────────────────┐
                                  │  返回 400            │
                                  │  THERAPIST_MISMATCH  │
                                  │  Phase 1: 只能由     │
                                  │  签约技师服务         │
                                  └─────────────────────┘
                    ┌──────────────────────────────────┐
                    │  [Phase 2] 排班冲突检测（暂不启用）  │
                    │  查 therapist_availability        │
                    │  + 同时段已有预约? → 409           │
                    └──────────────────────────────────┘
                         ┌──────────────┐
                         │   PENDING    │  待确认
                         │   (待管理员   │
                         │    审核)      │
                         └──────┬───────┘
                    ┌───────────┼───────────────┐
                    │ 管理员确认  │               │ 管理员拒绝或客户取消
                    │ /confirm   │               ▼
                    ▼           │      ┌──────────────────┐
            ┌──────────────┐   │      │    CANCELLED     │  已取消
            │  CONFIRMED   │   │      │  (记录取消原因)   │
            │  已确认       │   │      └──────────────────┘
            └──────┬───────┘   │      (来自 PENDING 或 CONFIRMED)
                   │           │
       课到当天     ├──── 管理员取消 ──────────────────────►CANCELLED
       管理员操作   │
          ┌────────┴────────────────────────┐
          │                                 │
          │ 客户到场                          │ 客户未到场
          │ /complete                        │ /no-show
          ▼                                 ▼
  ┌──────────────┐                ┌──────────────────┐
  │  COMPLETED   │                │    NO_SHOW       │
  │  已完成       │                │  (不扣课时)       │
  │              │                └──────────────────┘
  │ 自动触发（需行锁，Risk 3）:      │
  │ ① SELECT sessions FOR UPDATE  │
  │   (幂等检查，防重复完成)         │
  │ ② SELECT customer_packages    │
  │   FOR UPDATE (锁定课包行)       │
  │ ③ sessions_used += 1          │
  │ ④ 计算技师佣金                  │
  │ ⑤ COMMIT                      │
  │ ⑥ 若课包耗尽→package depleted  │
  └──────────────┘

注意:
• 管理员可直接创建 COMPLETED 状态记录（补录历史数据）
• NO_SHOW 默认不扣课时
• 只有 COMPLETED 触发课时扣减和佣金计算
• COMPLETED 的所有写操作须包裹在同一数据库事务内，第 2 个并发请求在幂等检查处返回 409
```

### 4.2 支付状态机 (Transaction State Machine)

**微信支付**:
```
  POST create-order
       │
       ▼
   PENDING ──── 超时/用户取消 ──► CANCELLED
       │
       ├── 支付成功（微信回调）──► PAID（终态）
       └── 支付失败 ──────────► FAILED

退款: 管理员创建 amount_fen < 0 的新交易记录，无需状态机
```

**银行转账**:
```
  Admin 录入
       │
       ▼
   PENDING ──── 管理员拒绝 ──► REJECTED（重新录入）
       │
       └── 管理员确认 ──────► CONFIRMED（终态）
```

### 4.3 课包生命周期 (Customer Package Lifecycle)

```
  Admin 创建课包记录
         │
         ▼
  PENDING_PAYMENT ──── 收到付款 ──► ACTIVE（正常使用）
                                        │
                            ┌───────────┼───────────────┐
                            │           │               │
                   sessions_used    超过 expiry_date  Admin 取消
                   == total+gifted       │               │
                            │           ▼               ▼
                            ▼        EXPIRED         CANCELLED
                        DEPLETED     (已超期)          (已取消)
                       (已耗尽)
```

### 4.4 转介绍奖励状态机 (Referral State Machine)

```
  新客户注册（传入 referral_code）
         │
         ▼
     PENDING ──── 超过有效期（Celery 每日检查）──► EXPIRED
         │
         ├── 被推荐人完成首次付款 ──► AWARDED（终态，加赠课时）
         └── Admin 手动取消 ──────► CANCELLED（终态）
```

---

## 5. 技术选型理由

### 5.1 Taro 4 + React（微信小程序）

| 对比 | 原生 WXML | **Taro 4 + React（选用）** |
|---|---|---|
| 语言 | JS（弱类型） | TypeScript（类型安全） |
| 语法 | 微信专有 | React 组件化，生态成熟 |
| 未来扩展 | 仅微信 | 可编译为 H5，Phase 2 Web 成本低 |

**理疗门店场景**: 单人开发需快速迭代；招外包更容易找 React 开发者。

### 5.2 Python FastAPI（后端）

| 对比 | Node.js NestJS | **Python FastAPI（选用）** |
|---|---|---|
| Phase 2 AI | 需桥接 Python 微服务 | **直接调用 LangChain/scikit-learn** |
| 微信 SDK | weixin-node（社区维护） | **wechatpy（成熟稳定）** |
| 自动文档 | 需额外配置 | **内置 /docs（Swagger）** |
| Excel 处理 | SheetJS | **openpyxl（中文支持更稳定）** |

### 5.3 PostgreSQL（数据库）

| 对比 | MySQL | **PostgreSQL（选用）** |
|---|---|---|
| JSON 支持 | 基础 | **JSONB（可索引查询，AI 数据必需）** |
| 数组类型 | 不支持 | **TEXT[]（body_areas 字段）** |
| 并发 | 基本 | **MVCC（多技师并发销课不冲突）** |

### 5.4 腾讯云（云服务）

1. 微信支付回调延迟最低（同网络）
2. ICP 备案审核最快（微信小程序域名必须备案）
3. TencentDB PostgreSQL 免运维，自动备份
4. COS 与微信生态无缝集成

### 5.5 Celery（异步任务）

理疗门店场景需要异步处理：
- **群发通知**: 500客户 × 微信API = 不能让 HTTP 请求同步等待
- **Excel 导出**: 数据查询+文件生成应在后台完成
- **转介绍到期**: 每日凌晨定时扫描 pending referrals

---

## 6. 微信小程序配置与部署

### 6.1 前置准备（必须完成）

| 步骤 | 平台 | 说明 |
|---|---|---|
| ① 注册小程序账号 | mp.weixin.qq.com | 类目：生活服务 → 健康/医疗 |
| ② 获取 AppID/AppSecret | 小程序后台 → 开发设置 | 存入 `.env`，不提交 Git |
| ③ 注册微信支付商户 | pay.weixin.qq.com | 需营业执照，个人主体不支持 |
| ④ 域名 ICP 备案 | 腾讯云控制台 | 小程序必须使用 HTTPS 且已备案域名 |
| ⑤ 配置服务器域名 | 小程序后台 → 服务器域名 | request合法域名：`https://api.yourdomain.com` |

### 6.2 project.config.json

```json
{
  "appid": "wxYOUR_APPID_HERE",
  "projectname": "pt-mgmt",
  "compileType": "miniprogram",
  "libVersion": "3.4.0",
  "setting": {
    "urlCheck": true,
    "es6": true,
    "enhance": true,
    "postcss": true,
    "minified": true,
    "nodeModules": true,
    "uploadWithSourceMap": true,
    "showShadowRootInWxmlPanel": true,
    "coverView": true
  },
  "condition": {
    "miniprogram": {
      "list": [
        { "name": "首页", "pathName": "pages/index/index", "query": "" },
        { "name": "登录调试", "pathName": "pages/login/index", "query": "" }
      ]
    }
  }
}
```

> ⚠️ 替换 `"appid"` 为微信公众平台获取的真实 AppID

### 6.3 Taro app.config.ts

```typescript
// miniprogram/src/app.config.ts
export default defineAppConfig({
  pages: [
    'pages/index/index',
    'pages/login/index',
    'pages/profile/index',
    'pages/packages/list',
    'pages/packages/detail',
    'pages/packages/my-packages',
    'pages/sessions/booking',
    'pages/sessions/list',
    'pages/sessions/detail',
    'pages/payment/wechat-pay',
    'pages/payment/bank-transfer',
    'pages/referral/index',
    'pages/notifications/index',
  ],
  window: {
    backgroundTextStyle: 'light',
    navigationBarBackgroundColor: '#ffffff',
    navigationBarTitleText: '理疗健康管理',
    navigationBarTextStyle: 'black',
  },
  permission: {
    'scope.userInfo': { desc: '用于完善您的会员档案' },
  },
  requiredPrivateInfos: ['getPhoneNumber'],
  sitemapLocation: 'sitemap.json',
})
```

### 6.4 环境变量 .env（模板）

```bash
# 微信小程序
WECHAT_APP_ID=wxYOUR_APPID
WECHAT_APP_SECRET=your_app_secret

# 微信支付
WECHAT_PAY_MCH_ID=your_mch_id
WECHAT_PAY_API_KEY_V3=your_v3_api_key
WECHAT_PAY_CERT_SERIAL_NO=your_cert_serial
WECHAT_PAY_NOTIFY_URL=https://api.yourdomain.com/api/v1/webhooks/wechat-pay

# 数据库
DATABASE_URL=postgresql://user:password@host:5432/ptmgmt

# Redis
REDIS_URL=redis://host:6379/0

# JWT
JWT_SECRET_KEY=your_very_long_random_secret_at_least_32_chars
JWT_ALGORITHM=HS256

# 腾讯云 COS
COS_SECRET_ID=your_cos_secret_id
COS_SECRET_KEY=your_cos_secret_key
COS_BUCKET=ptmgmt-files-1234567890
COS_REGION=ap-guangzhou
```

### 6.5 本地开发

```bash
cp .env.example .env      # 填入真实值
docker compose up -d      # 启动 PostgreSQL + Redis + FastAPI + Nginx
docker compose exec api alembic upgrade head   # 数据库迁移

cd miniprogram && npm install && npm run dev:weapp
# 打开微信开发者工具，导入 miniprogram/dist/

cd admin && npm install && npm run dev
# 浏览器访问 http://localhost:5173
```

### 6.6 生产部署

```bash
# 服务器端（腾讯云 CVM）
git clone https://github.com/yourname/pt-mgmt.git /opt/pt-mgmt
cd /opt/pt-mgmt && cp .env.example .env && nano .env
cd admin && npm install && npm run build && cd ..
docker compose -f docker-compose.prod.yml up -d
docker compose exec api alembic upgrade head

# 小程序发布
cd miniprogram && npm run build:weapp
# 微信开发者工具 → 上传 → 微信公众平台 → 版本管理 → 提审 → 发布
```

### 6.7 微信特有注意事项

| 注意点 | 说明 |
|---|---|
| HTTPS 强制 | `wx.request` 仅支持 HTTPS；开发时可关闭域名校验 |
| 域名白名单 | 更换域名后需在微信公众平台重新配置，24小时生效 |
| 手机号授权 | `getPhoneNumber` 需完成企业认证（个人主体不支持） |
| 订阅消息模板 | 需在公众平台申请对应模板，审核后获取 `template_id` |
| 包体积限制 | 主包 ≤ 2MB，总大小 ≤ 20MB；可配置 Taro 分包加载 |

---

## 7. Git 操作指南

### 7.1 初始化仓库

```bash
cd /home/franc/CC-Prj/PT-MGMT
git init

# .gitignore 已创建，包含：
# .env、project.private.config.json、node_modules/、
# __pycache__/、dist/、*.pem、*.key 等敏感文件

git add docs/ tech-stack.md .gitignore
git commit -m "docs: add architecture and tech-stack documentation"
```

### 7.2 分支策略

```
main      ← 生产代码（只合并经测试的内容）
  └─ develop  ← 日常开发主线
       ├─ feature/auth-wechat-login
       ├─ feature/customer-crud
       ├─ feature/session-booking
       └─ fix/payment-callback-error
```

```bash
git checkout -b develop
git checkout -b feature/auth-wechat-login
# 完成后:
git checkout develop && git merge feature/auth-wechat-login
git branch -d feature/auth-wechat-login
```

### 7.3 提交信息规范

```
格式: <类型>(<范围>): <描述>

feat(auth): add WeChat wx.login flow with JWT issuance
feat(sessions): implement session booking by customer
fix(payments): handle WeChat Pay callback signature verification failure
docs(api): update session state machine documentation
chore(docker): update docker-compose.yml production config
```

### 7.4 敏感文件警告

| ⚠️ 绝对不能提交 | 原因 |
|---|---|
| `.env` | 含 AppSecret、数据库密码、JWT 密钥 |
| `project.private.config.json` | 含小程序私有配置 |
| `*.pem`, `*.key` | 微信支付证书私钥 |

```bash
# 如果不小心提交了：
git rm --cached .env
git commit -m "chore: remove accidentally committed .env"
# 立即重置所有密钥！！！
```

---

---

## 8. 并发控制、排班冲突与账号打通

### 8.1 技师服务模式：Phase 1 vs Phase 2

#### Phase 1（当前实现）：售课即服务，单一技师负责制

**业务背景**: 门店当前模式是哪位技师销售课包，该技师即全程负责该客户的所有课时服务。客户与技师之间存在固定的一对一关系。

**Phase 1 后端校验逻辑**（`POST /sessions`）:

```sql
-- 校验技师身份：必须是课包的销售技师
SELECT sold_by_staff_id FROM customer_packages
WHERE id = :package_id;

-- 若 sold_by_staff_id != :therapist_id → 返回 400 THERAPIST_MISMATCH
```

**Phase 1 校验失败响应体**:

```json
{
  "success": false,
  "error": {
    "code": "THERAPIST_MISMATCH",
    "message": "Phase 1 限制：只能由销售该课包的技师提供服务。",
    "details": {
      "package_id": "cpkg_...",
      "expected_therapist_id": "stf_01J9...",
      "provided_therapist_id": "stf_02K0..."
    }
  }
}
```

**Phase 1 无需启用 `therapist_availability` 表**：在单一技师负责制下，同一技师的客户预约本身在时间上由技师自行调配（技师了解自己的日程），系统只需记录数据，不需要做跨技师冲突检测。

#### Phase 2（未来扩展）：多技师治疗方案模式

详见 [Section 8.4](#84-phase-2-多技师治疗方案预留设计)。届时启用 `therapist_availability` 表进行排班冲突检测，冲突时返回：

```json
{
  "success": false,
  "error": {
    "code": "THERAPIST_SCHEDULE_CONFLICT",
    "message": "该技师在此时段已有其他预约，请联系店长或选择其他时间。",
    "details": {
      "conflicting_session_id": "sess_01J9...",
      "therapist_id": "stf_01J9...",
      "requested_at": "2026-03-05T14:00:00+08:00"
    }
  }
}
```

---

### 8.2 微信 UnionID 跨平台账号打通（Risk 2）

**问题**: 同一微信用户在不同接入平台下 `openid` 不同（小程序 ≠ 公众号 ≠ PC Web 微信登录），若只存 `openid` 则 PC 管理后台与小程序客户端数据完全割裂。

**前提**: 小程序、PC Web（未来）必须在[微信开放平台](https://open.weixin.qq.com)绑定同一主体，`jscode2session` 才会返回 `unionid`。**上线前务必完成此绑定操作**，否则 `unionid` 为空，跨端合并无法实现。

**账号查找与合并策略**:

| 登录场景 | 查找顺序 | 合并逻辑 |
|---|---|---|
| 小程序 `wx.login` | 先查 `openid` → 再查 `unionid` | 若两者不同 user → 合并（保留最早创建的记录） |
| PC Web 微信扫码（Phase 2）| 先查 `unionid` → 再查 `openid` | 找到已有账号则直接登录，无需新建 |
| 手机号登录（Phase 2）| 查 `phone` | 若同时存在 `unionid` 则更新现有账号 |

**登录时的合并 SQL 逻辑**:

```sql
-- 小程序登录：优先以 unionid 查找，防止多端创建重复账号
SELECT * FROM users
WHERE unionid = :unionid AND deleted_at IS NULL
LIMIT 1;

-- 若未找到，回退到 openid
SELECT * FROM users
WHERE openid = :openid AND deleted_at IS NULL
LIMIT 1;

-- 若仍未找到，创建新用户（同时存储 openid + unionid）
INSERT INTO users (openid, unionid, wechat_nickname, ...)
VALUES (:openid, :unionid, :nickname, ...);
```

**JWT 中需携带 `wx_unionid`**（用于日志溯源与跨端调试）:

```json
{
  "sub": "usr_01J9XZ2M3N4K5P6Q7R8S9T0V",
  "role": "customer",
  "phone": "13800138000",
  "wx_openid": "oXXXXXXXXXXXXXXXXXXXXXXXX",
  "wx_unionid": "oYYYYYYYYYYYYYYYYYYYYYYYY",
  "staff_id": null,
  "iat": 1740700800,
  "exp": 1740787200
}
```

> ⚠️ **上线检查清单**
> 1. 在微信开放平台完成"移动应用/小程序关联"，确认 `jscode2session` 返回值含 `unionid`
> 2. `users.unionid` 列加唯一索引（已在 ERD 中定义），防止合并后重复写入
> 3. Phase 2 PC Web 登录接口实现时，必须先查 `unionid` 再建用户

---

### 8.3 销课并发行锁（Risk 3）

**问题**: 店长与技师可能同时调用 `PATCH /sessions/{id}/complete`，导致 `sessions_used` 被双重扣减（从剩余 5 次扣到 3 次而非 4 次），造成账目错误。

**方案**: 数据库行锁（`SELECT ... FOR UPDATE`）+ 事务 + 幂等检查

`complete_session()` 后端函数须严格按以下顺序执行：

```sql
BEGIN;

-- Step 1: 幂等检查，加行锁防止并发进入
SELECT status FROM sessions
WHERE id = :session_id
FOR UPDATE;
-- 若 status != 'confirmed' → ROLLBACK → 返回 409 SESSION_ALREADY_PROCESSED

-- Step 2: 锁定课包行，防止并发写入课时
SELECT sessions_used, sessions_total, sessions_gifted
FROM customer_packages
WHERE id = :package_id
FOR UPDATE;
-- 第 2 个并发请求在此阻塞，等待 Step 1 的事务提交/回滚后才继续
-- 若 sessions_used >= sessions_total + sessions_gifted → ROLLBACK → 返回 400

-- Step 3: 原子更新（在同一事务内）
UPDATE sessions
SET status = 'completed',
    completed_at = NOW(),
    session_type = :session_type,
    body_areas = :body_areas,
    clinical_notes = :clinical_notes,
    therapist_commission_fen = :commission
WHERE id = :session_id;

UPDATE customer_packages
SET sessions_used = sessions_used + 1
WHERE id = :package_id;

COMMIT;
```

**SQLAlchemy (AsyncIO) 实现参考**:

```python
# backend/routers/sessions.py
async def complete_session(session_id: UUID, body: CompleteSessionBody, db: AsyncSession):
    async with db.begin():
        # Step 1: 幂等行锁
        stmt = (
            select(Session)
            .where(Session.id == session_id)
            .with_for_update()
        )
        session = (await db.execute(stmt)).scalar_one_or_none()
        if not session or session.status != "confirmed":
            raise ConflictError("SESSION_ALREADY_PROCESSED")

        # Step 2: 课包行锁
        stmt = (
            select(CustomerPackage)
            .where(CustomerPackage.id == session.customer_package_id)
            .with_for_update()
        )
        package = (await db.execute(stmt)).scalar_one()
        if package.sessions_used >= package.sessions_total + package.sessions_gifted:
            raise BusinessError("PACKAGE_INSUFFICIENT_SESSIONS")

        # Step 3: 原子更新
        session.status = "completed"
        session.completed_at = datetime.now(tz=timezone.utc)
        session.therapist_commission_fen = calculate_commission(package, session)
        package.sessions_used += 1
        # db.begin() 上下文管理器在退出时自动 COMMIT 或 ROLLBACK
```

**并发时序保障**:

```
时间轴:   店长请求          技师请求
t=0:      FOR UPDATE ──────► 阻塞等待锁
t=1:      status='confirmed' ✓
t=2:      sessions_used += 1
t=3:      COMMIT ──────────► 锁释放，技师获得锁
t=4:                          status='completed' ≠ 'confirmed'
t=5:                          → ROLLBACK → 返回 409
```

---

### 8.4 Phase 2 多技师治疗方案预留设计

**业务背景**: 随着门店规模扩大，会引入"首席诊疗师接诊 → 出治疗方案 → 分配不同专项技师"的协作模式：

```
诊疗师（接诊）
  └─ 制定治疗方案
       ├─ 康复技师  负责「颈椎康复训练」课程
       └─ 功能技师  负责「功能性力量训练」课程
```

**数据库升级计划（Phase 2）**:

```
新增表: treatment_plans
┌──────────────────────────────────────────────────────────────┐
│                     treatment_plans                          │
├──────────────────────────────────────────────────────────────┤
│ PK  id                  UUID                                 │
│ FK  customer_id         UUID  → users.id                     │
│ FK  lead_therapist_id   UUID  → users.id  (首席诊疗师)        │
│     diagnosis_notes     TEXT  (评估结论)                      │
│     plan_items          JSONB (各专项安排)                    │
│     status              VARCHAR(20)  active/completed        │
│     created_at          TIMESTAMPTZ                          │
│     updated_at          TIMESTAMPTZ                          │
└──────────────────────────────────────────────────────────────┘

sessions 表新增:
│ FK  treatment_plan_id   UUID  → treatment_plans.id  (nullable)│
│     treatment_item_type VARCHAR(50)  rehabilitation/strength/...│
```

**Phase 1 → Phase 2 迁移路径**:

| 字段/规则 | Phase 1 | Phase 2 |
|---|---|---|
| `sessions.therapist_id` | 必须等于 `sold_by_staff_id` | 由 `treatment_plan` 独立指定 |
| `therapist_availability` | 建库不启用 | 启用，排班冲突检测生效 |
| 客户-技师关系 | 一对一（固定签约） | 一对多（按项目分配） |
| `sessions.treatment_plan_id` | NULL | 关联治疗方案 |

> Phase 1 建库时 `sessions.treatment_plan_id` 默认 NULL，升级 Phase 2 只需 `ALTER TABLE sessions ADD COLUMN treatment_plan_id UUID` 加 `therapist_availability` 逻辑开关，**不需要重建表结构**，平滑升级。

---

*文档结束 | 下一步: 在下一轮讨论中确认实施顺序，建议从后端 Auth 接口和数据库模型开始*
