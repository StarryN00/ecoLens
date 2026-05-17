"""一次性 bootstrap 脚本：创建/提升管理员账号。

为什么需要它？
- 旧实现把 "数据库里第 0 条用户" 直接判为 admin（auth.py 里 count==0 那段）。
- 那是一个 TOCTOU race：两个并发的注册请求都能读到 count==0，结果两边
  都把 is_admin 置成 True，从而产生多个意外管理员。
- 现在 `/api/v1/auth/register` 一律创建普通用户；只有本脚本能造 admin。

用法
----
确保 SECRET_KEY、DATABASE_URL 已在环境变量或 backend/.env 中配置好，然后：

    cd backend
    # 交互式（推荐，密码不会出现在 shell history 里）
    python -m scripts.create_admin --username alice

    # 也可以一把梭（注意密码会进 shell history，不推荐）
    python -m scripts.create_admin --username alice --password 'S3cret!' --email alice@example.com

    # 把已有普通用户提升为 admin
    python -m scripts.create_admin --username alice --promote

退出码
------
- 0  成功
- 1  参数/输入错误
- 2  数据库错误
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import sys
from typing import Optional

from sqlalchemy import select

# 允许 `python -m scripts.create_admin` 和 `python scripts/create_admin.py` 两种调用
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import AsyncSessionLocal, init_db  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models import User  # noqa: E402


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="创建或提升管理员账号")
    p.add_argument("--username", required=True, help="管理员用户名 (3-64 字符)")
    p.add_argument(
        "--password",
        default=None,
        help="管理员密码（>=6 字符）。不传则交互式输入（推荐）",
    )
    p.add_argument("--email", default=None, help="可选邮箱")
    p.add_argument(
        "--promote",
        action="store_true",
        help="若用户已存在，则把它提升为 admin（不需要 --password）",
    )
    return p.parse_args()


def _read_password_interactive() -> str:
    p1 = getpass.getpass("管理员密码: ")
    p2 = getpass.getpass("再次输入: ")
    if p1 != p2:
        print("两次密码不一致", file=sys.stderr)
        sys.exit(1)
    if len(p1) < 6:
        print("密码长度需 >= 6", file=sys.stderr)
        sys.exit(1)
    return p1


async def _run(args: argparse.Namespace) -> int:
    username: str = args.username.strip()
    if not (3 <= len(username) <= 64):
        print("用户名长度需在 3-64 之间", file=sys.stderr)
        return 1

    await init_db()

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.username == username))
        user: Optional[User] = result.scalar_one_or_none()

        if user is not None:
            if not args.promote:
                print(
                    f"用户 {username!r} 已存在；如要把它提升为 admin，"
                    "请加 --promote",
                    file=sys.stderr,
                )
                return 1
            if user.is_admin:
                print(f"用户 {username!r} 已经是 admin，无需操作")
                return 0
            user.is_admin = True
            user.is_active = True
            await db.commit()
            print(f"OK: {username!r} 已提升为 admin")
            return 0

        # 新建 admin
        password = args.password or _read_password_interactive()
        if len(password) < 6:
            print("密码长度需 >= 6", file=sys.stderr)
            return 1

        new_admin = User(
            username=username,
            email=args.email,
            hashed_password=hash_password(password),
            is_active=True,
            is_admin=True,
        )
        db.add(new_admin)
        try:
            await db.commit()
        except Exception as e:  # 例如 UNIQUE 冲突（race 下另一进程刚插入）
            await db.rollback()
            print(f"创建失败: {e}", file=sys.stderr)
            return 2
        await db.refresh(new_admin)
        print(f"OK: 创建 admin {username!r} id={new_admin.id}")
        return 0


def main() -> None:
    args = _parse_args()
    rc = asyncio.run(_run(args))
    sys.exit(rc)


if __name__ == "__main__":
    main()
