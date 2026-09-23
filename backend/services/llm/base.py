from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator

from pydantic import BaseModel


class LLMResponse(BaseModel):
    """统一的 LLM 响应结构"""

    content: str
    model_name: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    finish_reason: str | None = None


class LLMTruncatedError(RuntimeError):
    """上游达到 max_tokens 上限而提前截断输出，内容不完整"""


class LLMUpstreamError(RuntimeError):
    """上游服务在响应体内报告错误（例如流中途下发的限流通知）"""


class BaseLLMService(ABC):
    """LLM 抽象基类"""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        json_mode: bool = False,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """
        非流式文本生成。

        temperature 为 None 时沿用厂商默认值；
        json_mode 为 True 时要求厂商以结构化 JSON 输出（各适配器自行翻译为厂商参数）；
        max_tokens 为 None 时沿用厂商默认上限。
        """

    @abstractmethod
    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        json_mode: bool = False,
        max_tokens: int | None = None,
    ) -> AsyncGenerator[str, None]:
        """流式文本生成，语义与 generate 一致。输出被截断时抛出 LLMTruncatedError"""
