import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from schemas.atlas import AtlasGenerateRequest, AtlasResponse
from services import atlas
from services.llm.base import BaseLLMService
from services.llm.factory import LLMFactory

from routers.deps import require_api_token

router = APIRouter(
    prefix="/api",
    tags=["Atlas"],
    # 生成接口每次调用都会真实计费，整个路由组统一要求鉴权
    dependencies=[Depends(require_api_token)],
)

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲，保证实时推送
}


def _create_llm_service(provider: str) -> BaseLLMService:
    """
    按名称创建 LLM 服务实例；未注册或未配置密钥时抛 400。

    把工厂的 ValueError 翻译成 HTTP 状态码属于 Web 层职责，所以放在这里而不是
    services/llm/factory.py 里（那是个不依赖 Web 框架的纯注册表）。
    两个生成端点都必须在开流之前调用它，否则非法 provider 会退化成
    "200 + 流内 error 帧"，与非流式端点返回 400 的契约不一致。
    """
    try:
        return LLMFactory.create(provider=provider)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


def _to_sse(event: dict) -> str:
    """把事件字典封装成标准 SSE data 帧"""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


# 此处原先有一个基于关键词的 STEM 课题界限校验，因不具备实际判别力已移除。
# 课题界限校验仍是产品要求，计划后续交由专门的 agent 承担。


@router.post("/generate", response_model=AtlasResponse)
async def generate_atlas(request: AtlasGenerateRequest):
    """
    提交技术课题并生成图谱数据
    """
    llm_service = _create_llm_service(request.provider)
    return await atlas.generate(request.query, llm_service)


@router.post("/generate/stream")
async def generate_atlas_stream(request: AtlasGenerateRequest):
    """
    以 SSE 流式推送图谱生成进度与最终结果。

    provider 校验在开流之前完成，所以非法 provider 仍能得到真实的 400；
    一旦开始推送，HTTP 状态码就固定为 200，此后的错误只能作为 error 帧下发。
    """
    llm_service = _create_llm_service(request.provider)

    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            async for event in atlas.generate_stream(request.query, llm_service):
                yield _to_sse(event)
        except Exception as e:  # noqa: BLE001 -- SSE 开流后无法改状态码，必须兜底转 error 帧
            # 兜底：异常若穿透生成器，Starlette 会因响应体未正常收尾而把它整体丢弃，
            # 前端只会看到 200 + 空响应体，然后无限等待。必须转成 error 帧。
            yield _to_sse({"type": "error", "detail": f"生成过程异常: {e}"})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
