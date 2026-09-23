# 确保所有 LLM 适配器模块在包加载时自动注册到 LLMFactory
from services.llm import deepseek  # noqa: F401
