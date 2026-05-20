from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import get_settings

settings = get_settings()

# 创建异步引擎 - 支持 PostgreSQL 和 SQLite
database_url = settings.DATABASE_URL
if database_url.startswith("sqlite"):
    # SQLite 需要特殊配置
    engine = create_async_engine(
        database_url,
        echo=settings.DEBUG,
        future=True,
        connect_args={"check_same_thread": False},
    )
else:
    # PostgreSQL
    engine = create_async_engine(database_url, echo=settings.DEBUG, future=True)

# 创建会话工厂
AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

# 声明基类
Base = declarative_base()


def _to_sync_url(url: str) -> str:
    """把 async SQLAlchemy URL 转成同步驱动 URL。

    Celery worker 跑在普通线程里，没必要也不该新建/拆毁 event loop
    （见 #8）。同一份 DATABASE_URL 需要给 FastAPI（async）和 Celery（sync）
    两套引擎复用，转换规则：

        sqlite+aiosqlite:///./x.db      -> sqlite:///./x.db
        postgresql+asyncpg://u:p@h/db   -> postgresql+psycopg2://u:p@h/db
        postgresql://...                -> 原样返回（psycopg2 默认驱动）
        其他未识别驱动                  -> 原样返回（让 SQLAlchemy 自己报错）
    """
    if not url:
        return url
    # 切 scheme 部分
    if "://" not in url:
        return url
    scheme, rest = url.split("://", 1)
    parts = scheme.split("+")
    base = parts[0]
    if base == "sqlite":
        # stdlib sqlite3 是默认同步驱动
        return f"sqlite://{rest}"
    if base == "postgresql":
        # asyncpg / psycopg / 任意 async 驱动 -> 强制 psycopg2 同步
        return f"postgresql+psycopg2://{rest}"
    # 未识别的方言保持原样
    return url


# 同步引擎 - 仅供 Celery worker 使用
# pool_pre_ping=True 防止 Postgres 长连接被防火墙 / 服务端清掉后下次拿空连接
_sync_url = _to_sync_url(database_url)
if _sync_url.startswith("sqlite"):
    sync_engine = create_engine(
        _sync_url,
        echo=settings.DEBUG,
        future=True,
        connect_args={"check_same_thread": False},
    )
else:
    sync_engine = create_engine(
        _sync_url,
        echo=settings.DEBUG,
        future=True,
        pool_pre_ping=True,
    )

SyncSessionLocal = sessionmaker(
    bind=sync_engine, expire_on_commit=False, autoflush=False, autocommit=False
)


async def get_db():
    """依赖注入: 获取数据库会话"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """初始化数据库表"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
