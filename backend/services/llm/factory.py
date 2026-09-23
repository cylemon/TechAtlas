from collections.abc import Awaitable, Callable
from typing import ClassVar

from services.llm.base import BaseLLMService

# 1. 明确：类型别名是一个构建/生产服务对象的闭包函数
LLMBuilder = Callable[..., BaseLLMService]
# 应用关闭时的清理回调
ShutdownHook = Callable[[], Awaitable[None]]


class LLMFactory:
    """完全通用的 LLM 注册中心与工厂类，零厂商硬编码"""

    # 使用 ClassVar 规范静态注册表类型
    _registry: ClassVar[dict[str, LLMBuilder]] = {}
    _shutdown_hooks: ClassVar[list[ShutdownHook]] = []

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

    @classmethod
    def available_providers(cls) -> list[str]:
        """
        反查当前已注册的全部提供商名称。
        供前端动态渲染选择菜单，避免在前后端代码中硬编码厂商名。
        """
        return sorted(cls._registry.keys())

    @classmethod
    def on_shutdown(cls, hook: ShutdownHook) -> None:
        """
        注册应用关闭时的清理回调（例如适配器关闭自己共享的 HTTP 客户端）。

        有了这个注册表，main.py 就不必 import 任何具体厂商模块——
        否则"具体厂商只出现在适配器里"这条边界就破了。
        """
        cls._shutdown_hooks.append(hook)

    @classmethod
    async def shutdown(cls) -> None:
        """依次执行所有清理回调，由应用 lifespan 的关闭阶段调用"""
        for hook in cls._shutdown_hooks:
            await hook()
        cls._shutdown_hooks.clear()
