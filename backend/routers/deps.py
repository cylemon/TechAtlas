from functools import lru_cache

from config import AppSettings
from fastapi import Header, HTTPException, status


@lru_cache(maxsize=1)
def get_app_settings() -> AppSettings:
    """进程内缓存配置，避免每个请求都重读 .env"""
    return AppSettings()


async def require_api_token(x_api_key: str | None = Header(default=None)) -> None:
    """
    校验调用方身份；API_TOKEN 未配置时放行（本地开发模式，启动时会打印告警）。

    /api/generate 每次调用都会真实计费，部署到公网前必须设置 API_TOKEN。
    """
    expected = get_app_settings().API_TOKEN
    if not expected:
        return

    if x_api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少或错误的 X-API-Key",
        )
