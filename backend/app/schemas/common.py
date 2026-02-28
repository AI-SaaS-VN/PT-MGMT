"""
通用响应 Schema

提供所有 API 接口的标准响应结构（对应 architecture.md § 3.5）：

成功响应：
    {
        "success": true,
        "data": { ... },
        "message": "操作成功"
    }

错误响应：
    {
        "success": false,
        "error": {
            "code": "AUTH_001",
            "message": "无效的登录凭证",
            "details": null
        }
    }

分页响应（data 内嵌套）：
    {
        "success": true,
        "data": {
            "items": [ ... ],
            "total": 100,
            "page": 1,
            "page_size": 20,
            "total_pages": 5
        }
    }
"""

import math
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


# -----------------------------------------------------------------------
# 基础响应
# -----------------------------------------------------------------------


class SuccessResponse(BaseModel, Generic[T]):
    """通用成功响应包装器。"""

    success: bool = True
    data: T
    message: str = "操作成功"


class ErrorDetail(BaseModel):
    """错误详情结构。"""

    code: str = Field(..., description="业务错误码，如 AUTH_001")
    message: str = Field(..., description="人类可读的错误描述")
    details: dict | None = Field(None, description="附加调试信息（生产环境可不返回）")


class ErrorResponse(BaseModel):
    """通用错误响应包装器。"""

    success: bool = False
    error: ErrorDetail


# -----------------------------------------------------------------------
# 分页
# -----------------------------------------------------------------------


class PaginatedResponse(BaseModel, Generic[T]):
    """分页数据容器，嵌入 SuccessResponse.data 中使用。"""

    items: list[T]
    total: int = Field(..., description="总记录数")
    page: int = Field(..., description="当前页码（从 1 开始）")
    page_size: int = Field(..., description="每页条数")
    total_pages: int = Field(..., description="总页数")

    @classmethod
    def create(
        cls,
        items: list[T],
        total: int,
        page: int,
        page_size: int,
    ) -> "PaginatedResponse[T]":
        """工厂方法，自动计算 total_pages。"""
        total_pages = math.ceil(total / page_size) if page_size > 0 else 0
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
