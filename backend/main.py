from fastapi import FastAPI
from schemas.atlas import AtlasGenerateRequest, AtlasGenerateResponse
from services.domain_guard import validate_stem_domain

app = FastAPI(
    title="TechAtlas API",
    description="Backend service for TechAtlas knowledge mapping agent",
    version="0.1.0",
)


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.post("/api/generate", response_model=AtlasGenerateResponse)
async def generate_atlas(request: AtlasGenerateRequest):
    """
    提交技术课题，评估领域合规性并生成图谱
    """
    return validate_stem_domain(request.query)
