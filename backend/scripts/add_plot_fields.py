"""迁移脚本：给 inspection_tasks 加 plot_area_mu 和 forestry_sub_compartment 列（T2）。

幂等，可重复跑。兼容 SQLite + PostgreSQL。

用法
----
    cd backend
    SECRET_KEY=... DATABASE_URL=... python -m scripts.add_plot_fields

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

from app.core.config import get_settings  # noqa: E402
from app.core.database import _to_sync_url  # noqa: E402

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

_NEW_COLUMNS = [
    ("plot_area_mu", "FLOAT"),
    ("forestry_sub_compartment", "VARCHAR(50)"),
]


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


def _add_columns(conn, dialect: str) -> None:
    for col_name, col_type in _NEW_COLUMNS:
        if _column_exists(conn, dialect, "inspection_tasks", col_name):
            logger.info("inspection_tasks.%s 已存在，跳过", col_name)
            continue
        if dialect == "sqlite":
            conn.exec_driver_sql(
                f"ALTER TABLE inspection_tasks ADD COLUMN {col_name} {col_type}"
            )
        else:
            conn.execute(
                text(
                    f"ALTER TABLE inspection_tasks "
                    f"ADD COLUMN IF NOT EXISTS {col_name} {col_type}"
                )
            )
        logger.info("✓ 已添加 inspection_tasks.%s (%s)", col_name, col_type)


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
        with engine.begin() as conn:
            _add_columns(conn, dialect)
    except SQLAlchemyError as exc:
        logger.error("数据库错误: %s", exc)
        return 2
    finally:
        engine.dispose()

    logger.info("OK: plot_area_mu + forestry_sub_compartment 迁移完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
