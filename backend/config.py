"""应用级配置（与具体 LLM 供应商无关）。

ENV_FILE 锚定到本文件所在目录，而不是进程的当前工作目录——否则从仓库根目录
启动（uvicorn backend.main:app）时会静默读不到配置，表现为"API Key 未配置"。
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"


class AppSettings(BaseSettings):
    """应用级配置"""

    # 为空表示关闭鉴权（本地开发用）。部署到公网前必须设置
    API_TOKEN: str = ""

    # 允许跨域访问的前端来源，逗号分隔。
    # 刻意用 str 而不是 list[str]：pydantic-settings 对 list 类型字段会先按 JSON
    # 解析环境变量，"a,b" 这种人类友好的写法会直接报错。
    CORS_ALLOW_ORIGINS: str = (
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:5173,http://127.0.0.1:5173"
    )

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_allow_origins(self) -> list[str]:
        """把逗号分隔的配置拆成列表，顺带丢弃空项"""
        return [
            origin.strip()
            for origin in self.CORS_ALLOW_ORIGINS.split(",")
            if origin.strip()
        ]
