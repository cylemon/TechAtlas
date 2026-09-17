from collections.abc import Callable
from typing import ClassVar

from services.llm_base import BaseLLMService

# 1. 明确：类型别名是一个构建/生产服务对象的闭包函数
LLMBuilder = Callable[..., BaseLLMService]


class LLMFactory:
    """完全通用的 LLM 注册中心与工厂类，零厂商硬编码"""

    # 使用 ClassVar 规范静态注册表类型
    _registry: ClassVar[dict[str, LLMBuilder]] = {}

    @classmethod
    def register(cls, provider: str):
        """注册装饰器：将创建服务实例的构建器注册到指定 provider 名称下"""

        def decorator(builder: LLMBuilder) -> LLMBuilder:
            cls._registry[provider.lower().strip()] = builder
            return builder

        return decorator

    @classmethod
    def create(cls, provider: str, **kwargs) -> BaseLLMService:
        """根据前端传入的 provider 动态生成对应厂商的 LLM 服务实例"""
        if not provider or not provider.strip():
            raise ValueError("必须指定 LLM 提供商 (provider)")

        provider_key = provider.lower().strip()
        if provider_key not in cls._registry:
            raise ValueError(
                f"未注册的 LLM 提供商: '{provider}'。当前已注册可用提供商: {list(cls._registry.keys())}"
            )

        builder = cls._registry[provider_key]
        return builder(**kwargs)
