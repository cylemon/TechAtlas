import json

import pytest
import respx
from fastapi import HTTPException
from httpx import Response
from services import atlas
from services.llm.factory import LLMFactory

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"


def _service():
    return LLMFactory.create(provider="deepseek")


def _mock_completion(content: str, finish_reason: str = "stop") -> Response:
    """构造一个 DeepSeek 非流式响应，用于 respx 模拟"""
    return Response(
        200,
        json={
            "choices": [
                {"message": {"content": content}, "finish_reason": finish_reason}
            ],
            "model": "deepseek-chat",
        },
    )


def _sse_body(*deltas: str) -> bytes:
    """把若干个文本分片包装成 DeepSeek 的流式 SSE 响应体"""
    frames = [
        "data: " + json.dumps({"choices": [{"delta": {"content": d}}]}) + "\n\n"
        for d in deltas
    ]
    frames.append("data: [DONE]\n\n")
    return "".join(frames).encode("utf-8")


async def _collect_stream(provider: str = "deepseek") -> list[dict]:
    """跑一遍流式生成，收集全部事件"""
    service = LLMFactory.create(provider=provider)
    return [event async for event in atlas.generate_stream("AI Agent", service)]


def _node_json(node_id: str, category: str = "core_concept") -> str:
    return json.dumps(
        {
            "id": node_id,
            "label": node_id.upper(),
            "category": category,
            "description": f"{node_id} 的说明",
            "importance": 5,
        },
        ensure_ascii=False,
    )


def _index_of_stage(events: list[dict], stage: str) -> int:
    for index, event in enumerate(events):
        if event.get("type") == "stage" and event.get("stage") == stage:
            return index
    raise AssertionError(f"没有找到 stage={stage} 事件")


def _atlas_json(edges: list[dict] | None = None) -> str:
    return json.dumps(
        {
            "topic": "AI Agent",
            "summary": "AI Agent 是兼具感知、思考与执行能力的智能体体系。",
            "nodes": [
                {
                    "id": "agent_arch",
                    "label": "Agent 架构",
                    "category": "core_concept",
                    "description": "智能体核心控制逻辑",
                    "importance": 5,
                },
                {
                    "id": "rag",
                    "label": "RAG",
                    "category": "sub_technology",
                    "description": "检索增强生成",
                    "importance": 4,
                },
            ],
            "edges": edges if edges is not None else [],
            "cross_domain_ideas": [],
        },
        ensure_ascii=False,
    )


async def test_generate_atlas_success():
    """能解析 LLM 返回的 JSON，并兼容 Markdown 代码围栏"""
    with respx.mock:
        respx.post(DEEPSEEK_URL).mock(
            return_value=_mock_completion(f"```json\n{_atlas_json()}\n```")
        )

        result = await atlas.generate("AI Agent", _service())

    assert result.topic == "AI Agent"
    assert len(result.nodes) == 2
    assert result.nodes[0].id == "agent_arch"


async def test_dangling_edges_are_pruned():
    """指向不存在节点的边会被丢弃，避免前端图库因悬空边渲染失败"""
    edges = [
        {"source": "agent_arch", "target": "rag", "relation": "includes"},
        {"source": "agent_arch", "target": "ghost_node", "relation": "depends_on"},
        {"source": "ghost_node", "target": "rag", "relation": "enables"},
    ]

    with respx.mock:
        respx.post(DEEPSEEK_URL).mock(
            return_value=_mock_completion(_atlas_json(edges=edges))
        )

        result = await atlas.generate("AI Agent", _service())

    assert len(result.edges) == 1
    assert result.edges[0].target == "rag"


async def test_truncated_output_is_reported_as_502():
    """输出被 max_tokens 截断时，应给出明确的 502 而不是含糊的解析失败"""
    with respx.mock:
        respx.post(DEEPSEEK_URL).mock(
            return_value=_mock_completion(_atlas_json(), finish_reason="length")
        )

        with pytest.raises(HTTPException) as exc_info:
            await atlas.generate("AI Agent", _service())

    assert exc_info.value.status_code == 502
    assert "截断" in exc_info.value.detail


async def test_empty_content_is_reported_as_502():
    """DeepSeek JSON 模式偶发返回空内容，应给出明确提示"""
    with respx.mock:
        respx.post(DEEPSEEK_URL).mock(return_value=_mock_completion(""))

        with pytest.raises(HTTPException) as exc_info:
            await atlas.generate("AI Agent", _service())

    assert exc_info.value.status_code == 502
    assert "空内容" in exc_info.value.detail


async def test_unknown_category_is_rejected():
    """category 收窄为四值枚举后，越界取值必须在服务端被拦下"""
    illegal = _atlas_json().replace('"core_concept"', '"some_new_category"')

    with respx.mock:
        respx.post(DEEPSEEK_URL).mock(return_value=_mock_completion(illegal))

        with pytest.raises(HTTPException) as exc_info:
            await atlas.generate("AI Agent", _service())

    assert exc_info.value.status_code == 502
    assert "结构不符合约定" in exc_info.value.detail


async def test_pipe_joined_relation_is_rejected():
    """
    relation 只约束形式不约束词表：实测不同领域会衍生出各自的关系词，
    收成枚举会打死大部分生成。但"把多个候选值用竖线拼成一个字符串"
    这类病态输出必须拦下——prompt 模板里就是这个写法，模型有样学样的风险很高。
    """
    edges = [
        {
            "source": "agent_arch",
            "target": "rag",
            "relation": "includes | depends_on | enhances",
        }
    ]

    with respx.mock:
        respx.post(DEEPSEEK_URL).mock(
            return_value=_mock_completion(_atlas_json(edges=edges))
        )

        with pytest.raises(HTTPException) as exc_info:
            await atlas.generate("AI Agent", _service())

    assert exc_info.value.status_code == 502
    assert "结构不符合约定" in exc_info.value.detail


async def test_generate_sends_json_mode_and_max_tokens():
    """
    锁住出站请求体：DeepSeek 的 JSON 模式要求必须同时设置 max_tokens，
    否则输出可能被中途截断。没有这条断言的话，哪天重构把这两行删掉，
    其余用例依然全绿，线上才开始大批 502。
    """
    with respx.mock:
        route = respx.post(DEEPSEEK_URL).mock(
            return_value=_mock_completion(_atlas_json())
        )

        await atlas.generate("AI Agent", _service())

    sent = json.loads(route.calls[0].request.content)
    assert sent["response_format"] == {"type": "json_object"}
    assert sent["max_tokens"] == 4000
    assert sent["stream"] is False
    assert sent["temperature"] == 0.2
    assert sent["model"] == "deepseek-chat"


async def test_in_band_upstream_error_is_surfaced():
    """
    上游会在流中途用 {"error": {...}} 帧报告失败（如限流）。这类帧没有 choices
    字段，若不显式识别就会被判空逻辑静默跳过，最终以"JSON 解析失败"的面目呈现，
    把真实原因掩盖掉。
    """
    frames = [
        "data: "
        + json.dumps({"choices": [{"delta": {"content": '{"topic":"X"'}}]})
        + "\n\n",
        "data: " + json.dumps({"error": {"message": "Rate limit exceeded"}}) + "\n\n",
        "data: [DONE]\n\n",
    ]

    with respx.mock:
        respx.post(DEEPSEEK_URL).mock(
            return_value=Response(
                200,
                content="".join(frames).encode("utf-8"),
                headers={"content-type": "text/event-stream"},
            )
        )

        events = [
            event async for event in atlas.generate_stream("AI Agent", _service())
        ]

    assert events[-1]["type"] == "error"
    assert "Rate limit exceeded" in events[-1]["detail"]


# ------------------------------------------------------------------
# 增量提取：边生成边推送
# ------------------------------------------------------------------


def _mock_stream(body: bytes) -> None:
    respx.post(DEEPSEEK_URL).mock(
        return_value=Response(
            200, content=body, headers={"content-type": "text/event-stream"}
        )
    )


async def test_nodes_are_pushed_before_the_stream_finishes():
    """
    节点一写完就推送，不必等整份 JSON 完成。

    判别标准：node 事件必须出现在 parsing 阶段之前——parsing 是在 LLM 流
    结束后才发出的。若改为最后一次性推送，这个断言就会失败。
    """
    parts = [
        '{"topic":"AI Agent","summary":"概述","nodes":[',
        _node_json("agent_arch"),
        ",",
        _node_json("rag", category="sub_technology"),
        '],"edges":[{"source":"agent_arch","target":"rag","relation":"includes"}],',
        '"cross_domain_ideas":[]}',
    ]

    with respx.mock:
        _mock_stream(_sse_body(*parts))
        events = await _collect_stream()

    node_events = [e for e in events if e["type"] == "node"]
    edge_events = [e for e in events if e["type"] == "edge"]

    assert [e["node"]["id"] for e in node_events] == ["agent_arch", "rag"]
    assert len(edge_events) == 1
    assert edge_events[0]["edge"]["relation"] == "includes"

    # 关键断言：推送发生在流结束之前
    first_node_at = events.index(node_events[0])
    assert first_node_at < _index_of_stage(events, "parsing")
    assert events[-1]["type"] == "result"


async def test_incomplete_node_is_never_pushed():
    """半个节点对象绝不能推送出去——它还不是合法 JSON"""
    parts = [
        '{"topic":"AI Agent","summary":"概述","nodes":[',
        '{"id":"agent_arch","label":"Agent 架构","category":"core',  # 故意截断
    ]

    with respx.mock:
        _mock_stream(_sse_body(*parts))
        events = await _collect_stream()

    assert not any(e["type"] == "node" for e in events)
    assert events[-1]["type"] == "error"


async def test_edge_to_unknown_node_is_skipped_incrementally():
    """指向不存在节点的边不推送，与最终结果的剪枝行为保持一致"""
    parts = [
        '{"topic":"AI Agent","summary":"概述","nodes":[',
        _node_json("agent_arch"),
        '],"edges":[{"source":"agent_arch","target":"ghost","relation":"uses"}],',
        '"cross_domain_ideas":[]}',
    ]

    with respx.mock:
        _mock_stream(_sse_body(*parts))
        events = await _collect_stream()

    assert len([e for e in events if e["type"] == "node"]) == 1
    assert not any(e["type"] == "edge" for e in events)

    # 最终结果里这条边同样被剪掉，增量与最终结果一致
    assert events[-1]["type"] == "result"
    assert events[-1]["atlas"]["edges"] == []


async def test_invalid_node_is_not_pushed():
    """节点的 category 越界时不推送——前端只应接触已验证的数据"""
    parts = [
        '{"topic":"AI Agent","summary":"概述","nodes":[',
        _node_json("agent_arch", category="brand_new_category"),
        '],"edges":[],"cross_domain_ideas":[]}',
    ]

    with respx.mock:
        _mock_stream(_sse_body(*parts))
        events = await _collect_stream()

    assert not any(e["type"] == "node" for e in events)
    # 整份文档校验同样失败，最终以 error 收场
    assert events[-1]["type"] == "error"
