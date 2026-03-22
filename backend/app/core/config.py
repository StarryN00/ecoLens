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

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings():
    return Settings()
