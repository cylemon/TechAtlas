import asyncio
import json
from collections.abc import AsyncGenerator

import httpx
from config import ENV_FILE
from pydantic_settings import BaseSettings, SettingsConfigDict

from services.llm.base import (
    BaseLLMService,
    LLMResponse,
    LLMTruncatedError,
    LLMUpstreamError,
)
from services.llm.factory import LLMFactory


# ==========================================
# 1. 定义该厂商专属的配置模型
# ==========================================
class DeepSeekConfig(BaseSettings):
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"
    # 生成一张完整图谱属于长耗时请求，默认 30s 会误报超时
    DEEPSEEK_TIMEOUT: float = 90.0

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )


# ==========================================
# 2. 共享 HTTP 客户端
# ==========================================
# 每次请求新建 AsyncClient 的代价很高：实测本机约 900ms（主要是 SSL 上下文与
# 连接池初始化），而图谱生成本身才几秒，这笔开销占比可观，且直接推迟了第一个
# 字到达的时间。httpx 的 AsyncClient 设计上就是可共享、并发安全的。
#
# timeout 因此改为按请求传入，不再绑在客户端上。
#
# 客户端跟着事件循环走：httpx 的连接池绑定在创建它的循环上，跨循环复用会出错。
# 生产环境只有一个循环，等价于单例；测试里每个用例一个新循环，则各自拿到新客户端。
_shared_client: httpx.AsyncClient | None = None
_shared_client_loop: asyncio.AbstractEventLoop | None = None


def _get_client() -> httpx.AsyncClient:
    global _shared_client, _shared_client_loop

    loop = asyncio.get_running_loop()
    if (
        _shared_client is None
        or _shared_client.is_closed
        or _shared_client_loop is not loop
    ):
        _shared_client = httpx.AsyncClient()
        _shared_client_loop = loop

    return _shared_client


async def close_shared_client() -> None:
    """关闭共享客户端；由应用关闭阶段调用（见 LLMFactory.on_shutdown）"""
    global _shared_client, _shared_client_loop

    if _shared_client is not None and not _shared_client.is_closed:
        await _shared_client.aclose()
    _shared_client = None
    _shared_client_loop = None


# ==========================================
# 3. 核心服务类
# ==========================================
class DeepSeekService(BaseLLMService):
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float,
    ):
        # timeout 不给默认值：唯一来源是 DeepSeekConfig.DEEPSEEK_TIMEOUT，
        # 两处各写一个默认值迟早会改漏一处
        if not api_key:
            raise ValueError(
                "DeepSeek API Key 未配置，请在 .env 中设置 DEEPSEEK_API_KEY"
            )
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _build_messages(prompt: str, system_prompt: str | None) -> list[dict[str, str]]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages

    def _build_payload(
        self,
        prompt: str,
        system_prompt: str | None,
        *,
        stream: bool,
        temperature: float | None,
        json_mode: bool,
        max_tokens: int | None,
    ) -> dict:
        """把公共层的语义参数翻译成 DeepSeek 的请求体字段"""
        payload = {
            "model": self.model,
            "messages": self._build_messages(prompt, system_prompt),
            "stream": stream,
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        return payload

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        json_mode: bool = False,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        payload = self._build_payload(
            prompt,
            system_prompt,
            stream=False,
            temperature=temperature,
            json_mode=json_mode,
            max_tokens=max_tokens,
        )

        response = await _get_client().post(
            f"{self.base_url}/chat/completions",
            headers=self.headers,
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()

        choice = data["choices"][0]
        finish_reason = choice.get("finish_reason")
        if finish_reason == "length":
            raise LLMTruncatedError(
                f"DeepSeek 输出达到 max_tokens={max_tokens} 上限被截断"
            )

        usage = data.get("usage", {})
        return LLMResponse(
            content=choice["message"]["content"],
            model_name=self.model,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            finish_reason=finish_reason,
        )

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        json_mode: bool = False,
        max_tokens: int | None = None,
    ) -> AsyncGenerator[str, None]:
        payload = self._build_payload(
            prompt,
            system_prompt,
            stream=True,
            temperature=temperature,
            json_mode=json_mode,
            max_tokens=max_tokens,
        )

        async with _get_client().stream(
            "POST",
            f"{self.base_url}/chat/completions",
            headers=self.headers,
            json=payload,
            timeout=self.timeout,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue

                data_str = line[6:].strip()
                if data_str == "[DONE]":
                    break

                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                # 上游会在流中途用带内错误帧报告失败（如限流）。必须显式识别：
                # 否则它会被下面的 choices 判空逻辑静默跳过，最终以
                # "JSON 解析失败"的面目呈现，掩盖真实原因。
                error = data.get("error")
                if error:
                    message = (
                        error.get("message") if isinstance(error, dict) else str(error)
                    )
                    raise LLMUpstreamError(f"上游返回错误: {message}")

                choices = data.get("choices") or []
                if not choices:
                    continue

                choice = choices[0]
                if choice.get("finish_reason") == "length":
                    raise LLMTruncatedError(
                        f"DeepSeek 输出达到 max_tokens={max_tokens} 上限被截断"
                    )

                delta = (choice.get("delta") or {}).get("content", "")
                if delta:
                    yield delta


# ==========================================
# 3. 构建器与自动注册
# ==========================================
@LLMFactory.register("deepseek")
def build_deepseek_service(**override_kwargs) -> BaseLLMService:
    # 延迟实例化：在调用构建函数时才去实时读取 .env 文件或环境变量
    ds_config = DeepSeekConfig()

    api_key = override_kwargs.pop("api_key", ds_config.DEEPSEEK_API_KEY)
    base_url = override_kwargs.pop("base_url", ds_config.DEEPSEEK_BASE_URL)
    model = override_kwargs.pop("model", ds_config.DEEPSEEK_MODEL)
    timeout = override_kwargs.pop("timeout", ds_config.DEEPSEEK_TIMEOUT)

    return DeepSeekService(
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout=timeout,
        **override_kwargs,
    )


# 应用关闭时释放共享的 HTTP 客户端
LLMFactory.on_shutdown(close_shared_client)
