from pydantic import BaseModel, Field


class ProviderListResponse(BaseModel):
    """可用 LLM 提供商列表响应体"""

    providers: list[str] = Field(
        ...,
        description="当前已注册可用的提供商名称列表，可直接用于前端选择菜单",
        examples=[["deepseek"]],
    )
