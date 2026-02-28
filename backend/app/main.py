"""
FastAPI 应用入口

启动命令（开发环境）：
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

生产环境（通过 Docker）：
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

已注册路由前缀：
    /api/v1/auth    →  认证（微信登录、Token 刷新）

全局错误处理（对应 architecture.md § 3.5 标准错误格式）：
    - RequestValidationError → 422，包含字段级错误详情
    - HTTPException         → 透传 status_code，包装为 ErrorResponse 格式
    - 未处理异常            → 500，生产环境不暴露 traceback
"""

import logging

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.routers import auth
from app.schemas.common import ErrorDetail, ErrorResponse

# -----------------------------------------------------------------------
# 日志配置
# -----------------------------------------------------------------------
logging.basicConfig(
    level=logging.DEBUG if settings.APP_DEBUG else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------
# FastAPI 应用实例
# -----------------------------------------------------------------------
app = FastAPI(
    title="PT-MGMT API",
    description="物理疗法门店管理系统后端 API",
    version="0.1.0",
    # 生产环境关闭 docs（可根据需要开放内网访问）
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
)

# -----------------------------------------------------------------------
# CORS 中间件
# -----------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------------------------
# 全局异常处理器
# -----------------------------------------------------------------------


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """将 FastAPI HTTPException 包装为标准 ErrorResponse 格式。"""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=ErrorDetail(
                code=f"HTTP_{exc.status_code}",
                message=str(exc.detail),
            )
        ).model_dump(),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """将 Pydantic 验证错误包装为标准 ErrorResponse 格式，附带字段级错误详情。"""
    # 提取字段级错误
    field_errors: dict = {}
    for error in exc.errors():
        loc = " → ".join(str(part) for part in error["loc"] if part != "body")
        field_errors[loc] = error["msg"]

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            error=ErrorDetail(
                code="VALIDATION_ERROR",
                message="请求参数验证失败",
                details=field_errors,
            )
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """捕获所有未处理异常，生产环境不暴露内部错误信息。"""
    logger.exception("Unhandled exception for %s %s", request.method, request.url)
    message = str(exc) if settings.APP_DEBUG else "服务器内部错误，请稍后重试"
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error=ErrorDetail(
                code="INTERNAL_SERVER_ERROR",
                message=message,
            )
        ).model_dump(),
    )


# -----------------------------------------------------------------------
# 路由注册
# -----------------------------------------------------------------------
API_V1_PREFIX = "/api/v1"

app.include_router(auth.router, prefix=API_V1_PREFIX)

# -----------------------------------------------------------------------
# 健康检查
# -----------------------------------------------------------------------


@app.get("/health", tags=["运维"], summary="健康检查")
async def health_check() -> dict:
    """
    负载均衡器 / 容器编排健康探针。

    始终返回 HTTP 200（若应用能响应请求，即视为健康）。
    数据库连通性检查可在此扩展（Phase 2 运维需求）。
    """
    return {"status": "ok", "version": app.version}
