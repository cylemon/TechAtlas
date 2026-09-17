import json
from collections.abc import AsyncGenerator

import httpx
from pydantic_settings import BaseSettings, SettingsConfigDict

from services.llm_base import BaseLLMService, LLMResponse
from services.llm_factory import LLMFactory


# ==========================================
# 1. 定义该厂商专属的配置模型
# ==========================================
class DeepSeekConfig(BaseSettings):
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# ==========================================
# 2. 核心服务类 (保持不变)
# ==========================================
class DeepSeekService(BaseLLMService):
    def __init__(self, api_key: str, base_url: str, model: str, timeout: float = 30.0):
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

    async def generate(
        self, prompt: str, system_prompt: str | None = None
    ) -> LLMResponse:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

            usage = data.get("usage", {})
            return LLMResponse(
                content=data["choices"][0]["message"]["content"],
                model_name=self.model,
                prompt_tokens=usage.get("prompt_tokens"),
                completion_tokens=usage.get("completion_tokens"),
            )

    async def generate_stream(
        self, prompt: str, system_prompt: str | None = None
    ) -> AsyncGenerator[str, None]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
        }

        async with (
            httpx.AsyncClient(timeout=self.timeout) as client,
            client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
            ) as response,
        ):
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        delta = data["choices"][0]["delta"].get("content", "")
                        if delta:
                            yield delta
                    except json.JSONDecodeError:
                        continue


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

    return DeepSeekService(
        api_key=api_key,
        base_url=base_url,
        model=model,
        **override_kwargs,
    )
