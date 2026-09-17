from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator

from pydantic import BaseModel


class LLMResponse(BaseModel):
    """统一的 LLM 响应结构"""

    content: str
    model_name: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class BaseLLMService(ABC):
    """LLM 抽象基类"""

    @abstractmethod
    async def generate(
        self, prompt: str, system_prompt: str | None = None
    ) -> LLMResponse:
        """非流式文本生成"""

    @abstractmethod
    async def generate_stream(
        self, prompt: str, system_prompt: str | None = None
    ) -> AsyncGenerator[str, None]:
        """流式文本生成"""
