"""
Excel 历史数据一次性导入脚本

从 物理治疗门店客户信息V1.xlsx 读取数据，直接写入 PostgreSQL。

执行方式（项目根目录）：
    PYTHONPATH=backend venv/bin/python backend/scripts/import_excel.py

幂等性：课程、技师、客户均先查后建，重复执行不会产生重复数据。
"""

import asyncio
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import openpyxl
from dotenv import load_dotenv

# 确保从项目根目录执行时 app 包可以被找到
ROOT = Path(__file__).parent.parent.parent
EXCEL_PATH = ROOT / "物理治疗门店客户信息V1.xlsx"

# config.py 以 cwd 为基准查找 .env，但脚本从项目根运行时实际文件在 backend/.env
load_dotenv(Path(__file__).parent.parent / ".env", override=False)

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.course import Course
from app.models.customer_package import CustomerPackage
from app.models.staff_profile import StaffProfile
from app.models.user import User

# ── 课程种类映射 ────────────────────────────────────────────────────────────
COURSE_NAMES = {
    "康复": "康复治疗",
    "功能": "功能训练",
    "筋膜刀": "筋膜刀治疗",
    "拉伸": "拉伸训练",
}


# ── 日期解析 ────────────────────────────────────────────────────────────────
def parse_excel_date(val) -> date:
    """将 Excel 单元格的日期值统一转为 Python date。

    openpyxl 对部分单元格会直接返回 datetime，对另一部分（格式为文本的）
    返回整数（Excel 日期序列号）。统一处理两种情况。
    """
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    if isinstance(val, (int, float)):
        # Excel 日期原点：1899-12-30（含 1900 闰年 bug 修正）
        return date(1899, 12, 30) + timedelta(days=int(val))
    return date.today()


# ── 复合价格字段解析 ─────────────────────────────────────────────────────────
def parse_price_field(s: str) -> tuple[int, int, int]:
    """将 '单价 / 节数 / 总额' 字符串拆解为三个整数。

    示例：'300 / 70 / 21000' → (300, 70, 21000)
    """
    parts = [p.strip() for p in str(s).split("/")]
    return int(parts[0]), int(parts[1]), int(parts[2])


# ── 主逻辑 ───────────────────────────────────────────────────────────────────
async def main() -> None:
    if not EXCEL_PATH.exists():
        print(f"✗ 找不到文件：{EXCEL_PATH}", file=sys.stderr)
        sys.exit(1)

    async with AsyncSessionLocal() as db:

        # ── Step 1：Seed 课程 ───────────────────────────────────────────────
        courses: dict[str, Course] = {}
        seeded_courses = 0
        for type_key, course_name in COURSE_NAMES.items():
            result = await db.execute(select(Course).where(Course.name == course_name))
            course = result.scalar_one_or_none()
            if course is None:
                course = Course(
                    name=course_name,
                    course_type="package",
                    session_count=12,   # 占位默认值，实际购买节数存于 customer_packages
                    price_fen=0,        # 占位，实际成交价存于 customer_packages.agreed_price_fen
                    is_active=True,
                )
                db.add(course)
                await db.flush()
                seeded_courses += 1
            courses[type_key] = course
        print(f"  课程：{seeded_courses} 条新建，{len(courses) - seeded_courses} 条已存在")

        # ── Step 2：Seed 技师 Rebecca ──────────────────────────────────────
        result = await db.execute(
            select(User).where(User.display_name == "Rebecca", User.role == "staff")
        )
        rebecca = result.scalar_one_or_none()
        if rebecca is None:
            rebecca = User(
                role="staff",
                display_name="Rebecca",
                real_name="Rebecca",
                gender="unknown",
                is_active=True,
            )
            db.add(rebecca)
            await db.flush()
            staff_profile = StaffProfile(
                user_id=rebecca.id,
                specialty="康复, 功能训练, 筋膜刀, 拉伸",
                employment_type="full_time",
            )
            db.add(staff_profile)
            await db.flush()
            print("  技师：1 条新建（Rebecca）")
        else:
            print("  技师：Rebecca 已存在，跳过")

        # ── Step 3：解析 Excel ──────────────────────────────────────────────
        wb = openpyxl.load_workbook(EXCEL_PATH, read_only=True)
        ws = wb.active
        data_rows = list(ws.iter_rows(values_only=True))[1:]  # 跳过表头

        customers: dict[str, User] = {}   # display_name → User
        new_customers = 0
        new_packages = 0
        skipped = 0

        for row in data_rows:
            (
                _no,
                name,
                phone_raw,
                purchase_date_raw,
                course_type,
                price_str,
                sessions_used,
                sessions_remaining,
            ) = row

            # 数据校验
            if not name or not course_type or not price_str:
                skipped += 1
                continue
            name = str(name).strip()
            course_type = str(course_type).strip()
            if course_type not in courses:
                print(f"  ⚠ 未知课程类型 '{course_type}'，跳过行：{name}", file=sys.stderr)
                skipped += 1
                continue

            # 解析字段
            purchase_date = parse_excel_date(purchase_date_raw)
            _unit_price, _sessions_purchased, total_yuan = parse_price_field(price_str)
            sessions_used = int(sessions_used or 0)
            sessions_remaining = int(sessions_remaining or 0)
            sessions_total = sessions_used + sessions_remaining

            # 手机号：Excel 存为整数（如 13801848648），转为字符串
            phone_str: str | None = None
            if phone_raw:
                try:
                    phone_str = str(int(float(phone_raw)))
                except (ValueError, TypeError):
                    phone_str = str(phone_raw).strip() or None

            # ── 获取或创建客户 ──────────────────────────────────────────
            if name not in customers:
                result = await db.execute(
                    select(User).where(User.display_name == name, User.role == "customer")
                )
                customer = result.scalar_one_or_none()
                if customer is None:
                    customer = User(
                        role="customer",
                        display_name=name,
                        real_name=name,
                        phone=phone_str,
                        gender="unknown",
                        is_active=True,
                    )
                    db.add(customer)
                    await db.flush()
                    new_customers += 1
                customers[name] = customer

            customer = customers[name]

            # ── 创建课包 ────────────────────────────────────────────────
            pkg = CustomerPackage(
                customer_id=customer.id,
                course_id=courses[course_type].id,
                sold_by_staff_id=rebecca.id,
                purchase_date=purchase_date,
                sessions_total=sessions_total,
                sessions_used=sessions_used,
                sessions_gifted=0,
                agreed_price_fen=total_yuan * 100,
                amount_paid_fen=total_yuan * 100,
                payment_status="paid",
                notes=f"从 Excel 导入（原始记录 NO={_no}）",
            )
            db.add(pkg)
            new_packages += 1

        await db.commit()

    print("\n✓ 导入完成")
    print(f"  新建客户：{new_customers} 人")
    print(f"  已存在客户（多课包）：{len(customers) - new_customers} 人")
    print(f"  新建课包：{new_packages} 个")
    if skipped:
        print(f"  跳过行：{skipped} 行（数据缺失或课程类型未知）")


if __name__ == "__main__":
    asyncio.run(main())
