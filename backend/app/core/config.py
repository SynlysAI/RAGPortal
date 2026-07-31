"""应用配置,从环境变量加载。"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """RAGPortal 全局配置。"""

    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 认证
    auth_secret: str
    auth_token_expire_hours: int = 24

    # AI4MS
    ai4ms_api_base_url: str = ""
    ai4ms_base_url: str
    ai4ms_portal_url: str

    # WeKnora
    weknora_base_url: str
    weknora_api_key: str

    # 上传
    upload_max_size_mb: int = 100
    upload_concurrency: int = 5
    allowed_file_types: str = "pdf,doc,docx,xls,xlsx,ppt,pptx,md,txt,csv,html"

    # 缓存
    kb_list_cache_ttl: int = 300

    # 数据库
    sqlite_path: str = "data/ragportal.db"

    # CORS
    frontend_origin: str = "http://localhost:3002"

    # 部署
    app_env: str = "development"
    log_level: str = "INFO"

    @property
    def allowed_file_types_set(self) -> set[str]:
        """允许的文件扩展名集合(去空白、去前置点)。"""
        return {
            t.strip().lower().lstrip(".")
            for t in self.allowed_file_types.split(",")
            if t.strip()
        }

    @property
    def resolved_ai4ms_api_base_url(self) -> str:
        """返回 AI4MS API 基础地址。

        优先使用显式配置的 `AI4MS_API_BASE_URL`。
        未配置时，基于 `AI4MS_BASE_URL` 自动补齐 `/api/v1`。

        Returns:
            规范化后的 AI4MS API 基础地址。
        """
        api_base = self.ai4ms_api_base_url.strip().rstrip("/")
        if api_base:
            return api_base

        base_url = self.ai4ms_base_url.strip().rstrip("/")
        if base_url.endswith("/api/v1"):
            return base_url
        return f"{base_url}/api/v1"


@lru_cache
def get_settings() -> Settings:
    """单例 Settings。"""
    return Settings()
