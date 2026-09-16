from pydantic import BaseModel, Field


class AtlasGenerateRequest(BaseModel):
    """用户提交的技术探索请求"""

    query: str = Field(
        ..., min_length=2, max_length=100, description="技术课题或领域名称"
    )


class AtlasGenerateResponse(BaseModel):
    """后端生成的响应模型"""

    is_valid_domain: bool = Field(..., description="是否属于合法科技/STEM领域")
    query: str = Field(..., description="原始请求课题")
    reject_reason: str | None = Field(None, description="拦截原因（若非法）")
