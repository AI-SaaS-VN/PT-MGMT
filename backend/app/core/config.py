"""
应用配置模块

使用 Pydantic-Settings 自动读取 .env 文件中的环境变量。
所有配置集中在 Settings 类中，通过模块级单例 `settings` 访问。

用法：
    from app.core.config import settings
    print(settings.DATABASE_URL)
"""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用全局配置，对应 .env.example 中定义的所有变量。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",  # 忽略 .env 中多余的变量，便于扩展
    )

    # ---- 应用基础 ----
    APP_ENV: str = "development"      # development | staging | production
    APP_NAME: str = "PT-MGMT"
    APP_DEBUG: bool = True
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # ---- 数据库 ----
    DATABASE_URL: str = "postgresql://ptuser:ptpass@localhost:5432/ptmgmt"

    # ---- Redis ----
    REDIS_URL: str = "redis://localhost:6379/0"

    # ---- JWT ----
    JWT_SECRET_KEY: str = "CHANGE_ME_use_a_long_random_string_32chars_minimum"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_HOURS: int = 24
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ---- 微信小程序 ----
    WECHAT_APP_ID: str = ""
    WECHAT_APP_SECRET: str = ""

    # ---- 微信支付 v3（Phase 1 可不填）----
    WECHAT_PAY_MCH_ID: str = ""
    WECHAT_PAY_API_KEY_V3: str = ""
    WECHAT_PAY_CERT_SERIAL_NO: str = ""
    WECHAT_PAY_NOTIFY_URL: str = ""

    # ---- 腾讯云 COS ----
    COS_SECRET_ID: str = ""
    COS_SECRET_KEY: str = ""
    COS_BUCKET: str = ""
    COS_REGION: str = "ap-guangzhou"
    COS_BASE_URL: str = ""

    # ---- 业务参数 ----
    REFERRAL_EXPIRY_DAYS: int = 90   # 转介绍奖励有效期（天）

    # ---- 微信 API 基础 URL（测试可 mock）----
    WECHAT_API_BASE_URL: str = "https://api.weixin.qq.com"

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """确保 DATABASE_URL 不使用 asyncpg 前缀（由 database.py 统一处理）。"""
        if v.startswith("postgresql+asyncpg://"):
            return v.replace("postgresql+asyncpg://", "postgresql://")
        return v

    @property
    def async_database_url(self) -> str:
        """返回 asyncpg 格式的连接字符串，供 SQLAlchemy async engine 使用。"""
        url = self.DATABASE_URL
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        return url

    @property
    def allowed_origins_list(self) -> list[str]:
        """将逗号分隔的 ALLOWED_ORIGINS 字符串转为列表。"""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


# 模块级单例 —— 整个应用通过此对象访问配置
settings = Settings()
