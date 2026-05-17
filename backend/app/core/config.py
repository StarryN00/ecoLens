from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """应用配置"""

    # 应用
    APP_NAME: str = "樟巢螟智能检测系统"
    DEBUG: bool = True

    # 数据库
    DATABASE_URL: str = "postgresql+asyncpg://nestuser:nestpass@localhost:5432/nestdb"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Celery - 使用SQLite作为broker（本地开发模式）
    CELERY_BROKER_URL: str = "sqla+sqlite:///celerydb.sqlite"
    CELERY_RESULT_BACKEND: str = "db+sqlite:///celerydb.sqlite"

    # 文件存储
    UPLOAD_DIR: str = "./uploads"
    THUMBNAIL_DIR: str = "./thumbnails"

    # AI模型 - 虫巢检测
    NEST_DETECTION_MODEL_PATH: str = "./models/best.pt"
    CONFIDENCE_THRESHOLD: float = 0.5

    # AI模型 - 树种识别
    TREE_CLASSIFICATION_MODEL_PATH: str = "./models/best.pt"
    CAMPHOR_TREE_CLASS_ID: int = 1
    TREE_DETECTION_THRESHOLD: float = 0.05

    # 旧的模型路径（保持兼容）
    TREE_MODEL_PATH: str = "./models/best.pt"
    NEST_MODEL_PATH: str = "./models/best.pt"

    # JWT 鉴权
    # SECRET_KEY 没有默认值：必须通过环境变量（或 .env）显式配置
    # 生成方式: python -c "import secrets; print(secrets.token_urlsafe(32))"
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 小时

    # CORS 允许的来源（逗号分隔），生产环境必须显式指定
    CORS_ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    class Config:
        env_file = ".env"

    @property
    def cors_origins_list(self) -> list[str]:
        """将逗号分隔的 CORS 配置解析为列表"""
        return [
            origin.strip()
            for origin in self.CORS_ALLOWED_ORIGINS.split(",")
            if origin.strip()
        ]


@lru_cache()
def get_settings():
    return Settings()
