from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
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
