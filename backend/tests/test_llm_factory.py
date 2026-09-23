import pytest
from services.llm.factory import LLMFactory


def test_factory_missing_provider_arg():
    """验证未传或传空 provider 时的工厂校验逻辑"""
    with pytest.raises(ValueError, match="必须指定 LLM 提供商"):
        LLMFactory.create(provider="")


def test_factory_unregistered_provider():
    """验证传入未知 provider 时的异常处理"""
    with pytest.raises(ValueError, match="未注册的 LLM 提供商"):
        LLMFactory.create(provider="unknown_llm")


def test_factory_available_providers():
    """验证能反查已注册的提供商，且顺序稳定"""
    providers = LLMFactory.available_providers()

    assert "deepseek" in providers
    assert providers == sorted(providers)
