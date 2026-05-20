from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置"""

    # 应用
    APP_NAME: str = "樟巢螟智能检测系统"
    DEBUG: bool = True

    # 数据库 — 无默认值：必须通过环境变量显式配置，防止生产环境误连本地库
    DATABASE_URL: str

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Celery — CELERY_BROKER_URL 无默认值，防止生产环境误用 SQLite broker
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str = "db+sqlite:///celerydb.sqlite"

    # 文件存储
    UPLOAD_DIR: str = "./uploads"
    THUMBNAIL_DIR: str = "./thumbnails"

    # AI模型 - 虫巢检测
    NEST_DETECTION_MODEL_PATH: str = "./models/nest_det.pt"
    CONFIDENCE_THRESHOLD: float = 0.5

    # AI模型 - 树种识别
    TREE_CLASSIFICATION_MODEL_PATH: str = "./models/tree_seg.pt"
    CAMPHOR_TREE_CLASS_ID: int = 1
    TREE_DETECTION_THRESHOLD: float = 0.05

    # JWT 鉴权
    # SECRET_KEY 没有默认值：必须通过环境变量（或 .env）显式配置
    # 生成方式: python -c "import secrets; print(secrets.token_urlsafe(32))"
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 小时

    # CORS 允许的来源（逗号分隔），生产环境必须显式指定
    CORS_ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    # 可观测性 — 可选，未配置时不初始化
    SENTRY_DSN: str = ""

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

    @model_validator(mode="after")
    def _validate_cors_origins(self) -> "Settings":
        """启动期校验：CORS_ALLOWED_ORIGINS 解析后必须非空。

        旧实现里如果误把 CORS_ALLOWED_ORIGINS 设成空串或 "," 等只剩空白的
        值，cors_origins_list 会返回 [] 然后被 CORSMiddleware 静默吃掉，
        所有跨域请求都会失败但日志里没有任何信号。这里改为启动时 raise。
        """
        if not self.cors_origins_list:
            raise ValueError(
                "CORS_ALLOWED_ORIGINS 必须是非空的逗号分隔来源列表，"
                "例如 'http://localhost:5173,https://example.com'。"
                "当前解析结果为空，请检查 .env 或环境变量。"
            )
        return self


@lru_cache()
def get_settings():
    return Settings()
