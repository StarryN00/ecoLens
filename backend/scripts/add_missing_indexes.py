"""一次性运维脚本：给现存库补齐 P1 #11 的外键索引 + M2 ownership 列。

本项目当前**没有 Alembic**（也不打算在 P1 引入）。本脚本的作用是把
模型层 P1 加固 / M2 加固后**新增**的索引和列，在已运行的 dev / staging /
prod 库上幂等补上：

  1) 给所有 FK 列 CREATE INDEX IF NOT EXISTS
       - ix_images_task_id
       - ix_image_detections_image_id / task_id
       - ix_raw_nest_detections_image_id / task_id
       - ix_unique_nests_task_id
  2) 给 inspection_tasks 加 owner_id 列（VARCHAR(36)，FK 软声明），
     索引 ix_inspection_tasks_owner_id
  3) 把所有 owner_id IS NULL 的旧任务回填给"第一个 admin"
     - 没 admin？脚本 abort，提示先跑 scripts/create_admin.py

设计要点
--------
- **双兼容 SQLite + PostgreSQL**：
    * 索引：两边都支持 `CREATE INDEX IF NOT EXISTS`，统一一条 SQL。
    * 列存在性检测：SQLite 用 `PRAGMA table_info`，PostgreSQL 用
      `information_schema.columns`。两边都做 "ALTER TABLE ADD COLUMN
      IF NOT EXISTS"（PG 14+ 原生支持；SQLite 自己手动检测后再 ADD）。
    * 加 FK / NOT NULL 约束：SQLite 不支持 `ADD CONSTRAINT`，跳过；
      PG 上仅在 owner_id 已全部回填后才 ALTER COLUMN SET NOT NULL。
- **幂等**：可以重复跑，不会因列已存在 / 索引已存在而失败。
- **CONCURRENTLY 提醒**：本脚本默认普通 `CREATE INDEX`，会短暂锁表。
  生产数据量大、不能停服时，请手动改用：
      CREATE INDEX CONCURRENTLY ix_xxx ON yyy (zzz);
  （必须在事务外执行，本脚本不便包装。）

用法
----
    cd backend
    SECRET_KEY=... DATABASE_URL=... python -m scripts.add_missing_indexes

退出码
------
  0  成功
  1  数据库里没有任何 admin（owner_id 回填无落脚点）
  2  数据库错误
"""

from __future__ import annotations

import logging
import os
import sys
from typing import List

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

# 允许 `python -m scripts.add_missing_indexes` 和 `python scripts/add_missing_indexes.py`
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_settings  # noqa: E402
from app.core.database import _to_sync_url  # noqa: E402

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


# (index_name, table, column)
_INDEXES: List[tuple[str, str, str]] = [
    ("ix_images_task_id", "images", "task_id"),
    ("ix_image_detections_image_id", "image_detections", "image_id"),
    ("ix_image_detections_task_id", "image_detections", "task_id"),
    ("ix_raw_nest_detections_image_id", "raw_nest_detections", "image_id"),
    ("ix_raw_nest_detections_task_id", "raw_nest_detections", "task_id"),
    ("ix_unique_nests_task_id", "unique_nests", "task_id"),
    ("ix_inspection_tasks_owner_id", "inspection_tasks", "owner_id"),
]


def _dialect(engine: Engine) -> str:
    """返回 "sqlite" / "postgresql" / 其它原始 dialect.name"""
    return engine.dialect.name


def _column_exists(conn, dialect: str, table: str, column: str) -> bool:
    """SQLite 用 PRAGMA，PostgreSQL 用 information_schema。"""
    if dialect == "sqlite":
        # PRAGMA 不支持参数化绑定 table 名，但 table 名是硬编码常量
        rows = conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
        # PRAGMA table_info 返回 (cid, name, type, notnull, dflt_value, pk)
        return any(r[1] == column for r in rows)
    if dialect == "postgresql":
        result = conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = :t AND column_name = :c"
            ),
            {"t": table, "c": column},
        )
        return result.scalar() is not None
    # 其他 dialect：保守返回 False，让后续 ADD COLUMN 自然炸出来
    logger.warning("未知 dialect=%s，无法检测列存在性，假设不存在", dialect)
    return False


def _add_owner_id_column(conn, dialect: str) -> None:
    """给 inspection_tasks 加 owner_id 列（如果不存在）。

    SQLite：先 PRAGMA 检测，再 ALTER TABLE ADD COLUMN。SQLite 不支持
            ADD CONSTRAINT，所以加完列只能靠应用层保证 NOT NULL。
    PostgreSQL 14+ 直接 ADD COLUMN IF NOT EXISTS；老版本 PG 也支持
                同样语法（>= 9.6 起加 IF NOT EXISTS 给 ADD COLUMN）。
    """
    if _column_exists(conn, dialect, "inspection_tasks", "owner_id"):
        logger.info("inspection_tasks.owner_id 已存在，跳过 ADD COLUMN")
        return

    if dialect == "sqlite":
        # SQLite ALTER TABLE ADD COLUMN 不支持 IF NOT EXISTS（旧版本），
        # 但我们前面已 PRAGMA 过；nullable，因为旧行 owner 还没回填。
        conn.exec_driver_sql(
            "ALTER TABLE inspection_tasks ADD COLUMN owner_id VARCHAR(36)"
        )
    else:
        # PG / 其它支持 IF NOT EXISTS 的方言
        conn.execute(
            text(
                "ALTER TABLE inspection_tasks "
                "ADD COLUMN IF NOT EXISTS owner_id VARCHAR(36)"
            )
        )
    logger.info("✓ 已添加 inspection_tasks.owner_id 列")


def _ensure_indexes(conn, dialect: str) -> None:
    """对所有目标索引执行 CREATE INDEX IF NOT EXISTS。

    注意：生产 PG 上数据量大时请手动改用 `CREATE INDEX CONCURRENTLY`，
    本脚本图方便不用 CONCURRENTLY（它要求事务外执行，包起来复杂）。
    """
    for idx_name, table, column in _INDEXES:
        # 索引依赖列，所以列要先存在。owner_id 列由 _add_owner_id_column 兜底；
        # 其余列已经在 init_db 时建出来。
        if not _column_exists(conn, dialect, table, column):
            logger.warning(
                "%s.%s 不存在，跳过索引 %s（请先 init_db 建表）",
                table,
                column,
                idx_name,
            )
            continue
        conn.execute(
            text(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table} ({column})")
        )
        logger.info("✓ 索引就绪 %s ON %s(%s)", idx_name, table, column)


def _backfill_owner_id(conn, dialect: str) -> int:
    """把 owner_id IS NULL 的任务回填给第一个 admin。

    没 admin 直接 abort —— 回填没有合理 default，比静默留 NULL 安全。
    返回回填的行数。
    """
    if dialect == "sqlite":
        admin_row = conn.exec_driver_sql(
            "SELECT id FROM users WHERE is_admin = 1 ORDER BY created_at LIMIT 1"
        ).fetchone()
    else:
        admin_row = conn.execute(
            text(
                "SELECT id FROM users WHERE is_admin = TRUE "
                "ORDER BY created_at LIMIT 1"
            )
        ).fetchone()

    if admin_row is None:
        # 库里没 admin —— 没法决定 default owner
        return -1

    admin_id = admin_row[0]
    result = conn.execute(
        text(
            "UPDATE inspection_tasks SET owner_id = :oid "
            "WHERE owner_id IS NULL"
        ),
        {"oid": admin_id},
    )
    affected = result.rowcount or 0
    if affected:
        logger.info("✓ 回填 %d 条遗留任务的 owner_id = %s", affected, admin_id)
    else:
        logger.info("没有需要回填的任务")
    return affected


def _tighten_not_null(conn, dialect: str) -> None:
    """所有任务都回填后，把 owner_id 加 NOT NULL（仅 PG 支持）。

    SQLite 不支持 ALTER COLUMN，跳过 —— 应用层模型 NOT NULL 已经
    阻止新写入 NULL；旧库的 NOT NULL 约束只能等下次表重建。
    """
    if dialect == "sqlite":
        logger.info("SQLite 不支持 ALTER COLUMN SET NOT NULL，跳过约束加固")
        return
    if dialect != "postgresql":
        logger.info("dialect=%s，跳过约束加固", dialect)
        return
    # 仅 PG：先确认没有残余 NULL，再设 NOT NULL
    remain = conn.execute(
        text("SELECT COUNT(*) FROM inspection_tasks WHERE owner_id IS NULL")
    ).scalar()
    if remain:
        logger.warning(
            "仍有 %d 条 owner_id IS NULL，无法 SET NOT NULL，请检查回填",
            remain,
        )
        return
    conn.execute(
        text("ALTER TABLE inspection_tasks ALTER COLUMN owner_id SET NOT NULL")
    )
    logger.info("✓ inspection_tasks.owner_id 已设为 NOT NULL（PG）")


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
            # 1) 先加列（不存在则补）
            _add_owner_id_column(conn, dialect)
            # 2) 再加索引（包括 owner_id 上的索引）
            _ensure_indexes(conn, dialect)
            # 3) 回填遗留任务的 owner_id
            backfilled = _backfill_owner_id(conn, dialect)
            if backfilled < 0:
                logger.error(
                    "未找到任何 admin 用户。请先：python -m scripts.create_admin --username ..."
                )
                return 1
            # 4) PG 上把列收紧为 NOT NULL（SQLite 跳过）
            _tighten_not_null(conn, dialect)
    except SQLAlchemyError as exc:
        logger.error("数据库错误: %s", exc)
        return 2
    finally:
        engine.dispose()

    logger.info("OK: 索引 + owner_id 迁移完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
