import pytest
from services.llm_factory import LLMFactory


def test_factory_missing_provider_arg():
    """验证未传或传空 provider 时的工厂校验逻辑"""
    with pytest.raises(ValueError, match="必须指定 LLM 提供商"):
        LLMFactory.create(provider="")


def test_factory_unregistered_provider():
    """验证传入未知 provider 时的异常处理"""
    with pytest.raises(ValueError, match="未注册的 LLM 提供商"):
        LLMFactory.create(provider="unknown_llm")
