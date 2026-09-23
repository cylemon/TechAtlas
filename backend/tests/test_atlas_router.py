import json

import respx
from httpx import Response

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"

ATLAS = {
    "topic": "Quantum Computing",
    "summary": "量子计算利用量子力学特性进行运算。",
    "nodes": [
        {
            "id": "qubit",
            "label": "量子比特",
            "category": "core_concept",
            "description": "量子计算的基本信息单元",
            "importance": 5,
        }
    ],
    "edges": [],
    "cross_domain_ideas": [],
}


def _mock_stream_body(json_text: str, piece: int = 20) -> bytes:
    """把一段 JSON 文本切碎，模拟 DeepSeek 的流式 SSE 分片响应"""
    frames = []
    for i in range(0, len(json_text), piece):
        chunk = {"choices": [{"delta": {"content": json_text[i : i + piece]}}]}
        frames.append(f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n")
    frames.append("data: [DONE]\n\n")
    return "".join(frames).encode("utf-8")


def _parse_sse_events(body: str) -> list[dict]:
    return [
        json.loads(frame[len("data: ") :])
        for frame in body.strip().split("\n\n")
        if frame.startswith("data: ")
    ]


# ------------------------------------------------------------------
# 1. POST /api/generate 非流式
# ------------------------------------------------------------------


def test_generate_atlas_returns_graph(test_client):
    """有效的技术课题应返回结构化图谱"""
    mock_llm_response = {
        "choices": [{"message": {"content": json.dumps(ATLAS, ensure_ascii=False)}}],
        "model": "deepseek-chat",
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }

    with respx.mock:
        respx.post(DEEPSEEK_URL).mock(return_value=Response(200, json=mock_llm_response))

        response = test_client.post(
            "/api/generate",
            json={"query": "Quantum Computing Fundamentals", "provider": "deepseek"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["topic"] == "Quantum Computing"
    assert len(data["nodes"]) == 1
    assert data["nodes"][0]["id"] == "qubit"


def test_generate_atlas_rejects_empty_query(test_client):
    """空查询应被 Pydantic Schema 拦下"""
    response = test_client.post("/api/generate", json={"query": "", "provider": "deepseek"})

    assert response.status_code in [400, 422]


def test_generate_atlas_rejects_unknown_provider(test_client):
    """未注册的 provider 应返回 400"""
    response = test_client.post(
        "/api/generate",
        json={"query": "Quantum Computing Fundamentals", "provider": "unknown_llm"},
    )

    assert response.status_code == 400
    assert "未注册的 LLM 提供商" in response.json()["detail"]


# ------------------------------------------------------------------
# 2. POST /api/generate/stream SSE 进度流
# ------------------------------------------------------------------


def test_generate_atlas_stream_emits_stages_then_result(test_client):
    """流式接口应按 生成中 → 解析中 → 结果 的顺序推送事件"""
    with respx.mock:
        respx.post(DEEPSEEK_URL).mock(
            return_value=Response(
                200,
                content=_mock_stream_body(json.dumps(ATLAS, ensure_ascii=False)),
                headers={"content-type": "text/event-stream"},
            )
        )

        response = test_client.post(
            "/api/generate/stream",
            json={"query": "Quantum Computing Fundamentals", "provider": "deepseek"},
        )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

    events = _parse_sse_events(response.text)

    assert events[0]["type"] == "stage"
    assert events[0]["stage"] == "generating"
    assert events[0]["label"]  # 阶段文案字段名固定为 label
    assert events[-2]["type"] == "stage"
    assert events[-2]["stage"] == "parsing"
    assert events[-1]["type"] == "result"
    assert events[-1]["atlas"]["topic"] == "Quantum Computing"
    assert events[-1]["atlas"]["nodes"][0]["id"] == "qubit"


def test_generate_atlas_stream_rejects_unknown_provider_before_streaming(test_client):
    """未注册的 provider 必须在开流之前返回 400，而不是 200 + error 帧"""
    response = test_client.post(
        "/api/generate/stream",
        json={"query": "Quantum Computing Fundamentals", "provider": "unknown_llm"},
    )

    assert response.status_code == 400
    assert "未注册的 LLM 提供商" in response.json()["detail"]


def test_generate_atlas_stream_reports_upstream_failure_in_band(test_client):
    """
    上游失败时响应头早已发出，状态码固定为 200，错误只能作为 error 帧下发。
    这条测试把该约定固定下来：前端不能靠 HTTP 状态码判断成败。
    """
    with respx.mock:
        respx.post(DEEPSEEK_URL).mock(return_value=Response(500, json={"error": "boom"}))

        response = test_client.post(
            "/api/generate/stream",
            json={"query": "Quantum Computing Fundamentals", "provider": "deepseek"},
        )

    assert response.status_code == 200

    events = _parse_sse_events(response.text)
    assert events[-1]["type"] == "error"
    assert "LLM 调用失败" in events[-1]["detail"]
    assert not any(e["type"] == "result" for e in events)
