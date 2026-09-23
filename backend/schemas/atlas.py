from typing import Literal

from pydantic import BaseModel, Field


class AtlasGenerateRequest(BaseModel):
    """用户提交的技术探索请求"""

    query: str = Field(
        ..., min_length=2, max_length=100, description="技术课题或领域名称"
    )
    provider: str = Field(
        ...,
        description="必须显式指定 LLM 提供商名称，可通过 GET /api/providers 获取可选值",
        examples=["deepseek"],
    )


class AtlasNode(BaseModel):
    """图谱中的单一技术节点"""

    id: str = Field(
        ...,
        description="节点的唯一标识符，建议使用蛇形命名，如 'agent_architecture'",
    )
    label: str = Field(..., description="节点的展示名称，如 'Agent 架构类型'")
    category: Literal["core_concept", "sub_technology", "tool", "frontier"] = Field(
        ...,
        description="节点分类，前端据此为节点着色，取值受限以避免出现无法渲染的类别",
    )
    description: str = Field(..., description="该技术节点的简要核心阐述（1-2句话）")
    importance: int = Field(
        default=3,
        ge=1,
        le=5,
        description="技术重要程度/权重，1-5，可用于前端控制节点大小或颜色",
    )


class AtlasEdge(BaseModel):
    """节点之间的逻辑关联关系"""

    source: str = Field(..., description="起始节点的 id")
    target: str = Field(..., description="目标节点的 id")
    relation: str = Field(
        ...,
        # 只约束形式、不约束词表：实测不同领域会自然衍生新关系词
        # （三次调用产出 18 个互不重叠的取值），收成枚举会让大部分生成直接失败。
        # 这里挡住的是"把多个候选值用竖线拼成一个字符串"这类病态输出。
        pattern=r"^[a-z][a-z0-9_]*$",
        description=(
            "关系的蛇形命名描述，如 includes、depends_on、enables、implements、"
            "alternative_to。词表开放，但必须是单个小写蛇形词，不得用竖线拼接多个候选值"
        ),
    )


class AtlasResponse(BaseModel):
    """TechAtlas 全景图谱响应根结构"""

    topic: str = Field(..., description="评估的技术课题名称")
    summary: str = Field(..., description="该技术全景的全局概括与发展现状简介")
    nodes: list[AtlasNode] = Field(..., description="图谱的所有技术节点列表")
    edges: list[AtlasEdge] = Field(..., description="节点间的关系连线列表")
    cross_domain_ideas: list[str] | None = Field(
        default=[],
        description="架构留白：该技术课题潜在的跨领域融合思考方向（远景扩展预留）",
    )
