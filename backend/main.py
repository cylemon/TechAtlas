import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from routers.atlas_router import router as atlas_router
from routers.deps import get_app_settings
from schemas.provider import ProviderListResponse
from services.llm.factory import LLMFactory

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_app_settings()
    if not settings.API_TOKEN:
        logger.warning(
            "API_TOKEN 未配置：生成接口处于开放状态，任何调用方都会产生真实费用。"
            "部署到公网前请在 .env 中设置"
        )
    # 前端连不上时，第一件该看的就是这一行
    logger.info("允许的跨域来源: %s", settings.cors_allow_origins)
    yield
    # 让各适配器释放自己持有的资源（如共享的 HTTP 客户端）
    await LLMFactory.shutdown()


app = FastAPI(
    title="TechAtlas API",
    description="Backend service for TechAtlas knowledge mapping agent",
    version="0.1.0",
    lifespan=lifespan,
)

# ------------------------------------------------------------------
# 配置 CORS 跨域中间件（来源由 CORS_ALLOW_ORIGINS 环境变量决定）
# ------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_app_settings().cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有 HTTP 方法 (GET, POST, OPTIONS 等)
    allow_headers=["*"],  # 允许所有 Headers
    expose_headers=["*"],  # 暴露响应头给前端 JS/Fetch 流提取
)


# ------------------------------------------------------------------
# 注册业务路由
# ------------------------------------------------------------------
app.include_router(atlas_router)


# ------------------------------------------------------------------
# 服务自身信息路由（不归属于任何业务域）
# ------------------------------------------------------------------
@app.get("/", tags=["System"])
async def root():
    return {
        "message": "Welcome to TechAtlas API",
        "docs": "/docs",
        "health": "/health",
        "ready": "/ready",
        "providers": "/api/providers",
    }


@app.get("/health", tags=["System"])
async def health_check():
    """
    存活探针：只回答"进程还在不在"。

    刻意不检查任何外部依赖——否则编排系统会把一个本身健康的进程
    因为下游抖动而反复重启。配置类问题请查 /ready。
    """
    return {"status": "ok"}


@app.get("/ready", tags=["System"])
async def readiness_check(response: Response):
    """
    就绪探针：本实例是否具备对外服务的能力。

    只做本地配置检查，**不发起上游调用**——探针会被高频轮询，
    让它去 ping 模型服务等于按探针频率烧钱。
    构造 LLM 实例是纯本地操作（读配置、校验密钥非空），不产生网络请求。
    """
    problems: list[str] = []
    warnings: list[str] = []

    if not get_app_settings().API_TOKEN:
        warnings.append("API_TOKEN 未配置，生成接口处于开放状态")

    providers = LLMFactory.available_providers()
    if not providers:
        problems.append("没有任何已注册的 LLM 提供商")
    for provider in providers:
        try:
            LLMFactory.create(provider=provider)
        except ValueError as e:
            problems.append(f"{provider}: {e}")

    if problems:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "unavailable",
            "providers": providers,
            "problems": problems,
            "warnings": warnings,
        }

    return {"status": "ok", "providers": providers, "warnings": warnings}


@app.get("/api/providers", response_model=ProviderListResponse, tags=["Providers"])
async def list_providers():
    """列出当前已注册的 LLM 提供商，供前端渲染选择菜单"""
    return ProviderListResponse(providers=LLMFactory.available_providers())
