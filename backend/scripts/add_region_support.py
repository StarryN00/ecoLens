"""迁移脚本：T1 多级目录架构。

做两件事，幂等可重复跑，兼容 SQLite + PostgreSQL：
  1) 建 regions 表（市/区/街镇三级树）—— 全新表，用 create_all 建
  2) 给 inspection_tasks 加 region_id 列 + 索引 ix_inspection_tasks_region_id

注意：存量 inspection_tasks 行的 region_id 会是 NULL（无法回填——历史任务
没有区域信息）。模型层 region_id 本就 nullable；"新建任务必须选区域" 的
强制在 API 层（tasks.py）做。

用法
----
    cd backend
    SECRET_KEY=... DATABASE_URL=... python -m scripts.add_region_support

退出码
------
  0  成功
  2  数据库错误
"""

from __future__ import annotations

import logging
import os
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import models  # noqa: E402,F401  触发 Base.metadata 注册全部表
from app.core.config import get_settings  # noqa: E402
from app.core.database import Base, _to_sync_url  # noqa: E402

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def _dialect(engine: Engine) -> str:
    return engine.dialect.name


def _column_exists(conn, dialect: str, table: str, column: str) -> bool:
    if dialect == "sqlite":
        rows = conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
        return any(r[1] == column for r in rows)
    result = conn.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    )
    return result.scalar() is not None


def main() -> int:
    settings = get_settings()
    sync_url = _to_sync_url(settings.DATABASE_URL)
    if not sync_url:
        print("DATABASE_URL 未设置", file=sys.stderr)
        return 2

    logger.info("连接数据库 dialect=%s", sync_url.split("://", 1)[0])
    engine = create_engine(sync_url, future=True)
    try:
        dialect = _dialect(engine)

        # 1) 建缺失的表。regions 是全新表会被创建；users / inspection_tasks
        #    等已存在的表 create_all 默认 checkfirst=True 自动跳过。
        Base.metadata.create_all(engine)
        logger.info("✓ regions 表就绪")

        # 2) inspection_tasks 加 region_id 列 + 索引
        with engine.begin() as conn:
            if _column_exists(conn, dialect, "inspection_tasks", "region_id"):
                logger.info("inspection_tasks.region_id 已存在，跳过 ADD COLUMN")
            else:
                if dialect == "sqlite":
                    conn.exec_driver_sql(
                        "ALTER TABLE inspection_tasks "
                        "ADD COLUMN region_id VARCHAR(36)"
                    )
                else:
                    conn.execute(
                        text(
                            "ALTER TABLE inspection_tasks "
                            "ADD COLUMN IF NOT EXISTS region_id VARCHAR(36)"
                        )
                    )
                logger.info("✓ 已添加 inspection_tasks.region_id 列")

            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_inspection_tasks_region_id "
                "ON inspection_tasks (region_id)"
            )
            logger.info("✓ 索引 ix_inspection_tasks_region_id 就绪")
    except SQLAlchemyError as exc:
        logger.error("数据库错误: %s", exc)
        return 2
    finally:
        engine.dispose()

    logger.info("OK: regions 表 + inspection_tasks.region_id 迁移完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
