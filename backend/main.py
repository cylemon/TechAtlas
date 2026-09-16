from fastapi import FastAPI

app = FastAPI(
    title="TechAtlas API",
    description="Backend service for TechAtlas knowledge mapping agent",
    version="0.1.0",
)


@app.get("/health")
async def health_check():
    """
    健康检查探针接口
    用于验证服务运行状态与探针连通性
    """
    return {"status": "ok"}
