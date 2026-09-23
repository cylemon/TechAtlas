import pytest
import respx
from httpx import Response
from services.llm.factory import LLMFactory

# ------------------------------------------------------------------
# 1. 真实网络测试 (Live Integration Tests)
# ------------------------------------------------------------------


@pytest.mark.live
async def test_deepseek_live_generate():
    """真实调用 DeepSeek API，验证非流式生成"""
    service = LLMFactory.create(provider="deepseek")
    response = await service.generate(prompt="请用一句话回答：1+1等于几？")

    assert response.content is not None
    assert len(response.content) > 0
    assert response.model_name == "deepseek-chat"
    assert response.prompt_tokens is not None and response.prompt_tokens > 0


@pytest.mark.live
async def test_deepseek_live_generate_stream():
    """真实调用 DeepSeek API，验证 SSE 流式输出"""
    service = LLMFactory.create(provider="deepseek")
    chunks = []
    async for chunk in service.generate_stream(prompt="按顺序输出数字：1, 2, 3"):
        chunks.append(chunk)

    full_response = "".join(chunks)
    assert len(chunks) > 1
    assert "1" in full_response or "2" in full_response


# ------------------------------------------------------------------
# 2. 本地单元测试 (模拟边界异常与 SSE 数据容错)
# ------------------------------------------------------------------


async def test_deepseek_generate_stream_malformed_lines():
    """验证 generate_stream 遇到心跳包、坏 JSON 或异常格式时能优雅跳过而不崩溃"""
    # 使用工厂创建实例，传入自定义 api_key 覆盖配置，自动补全默认 base_url 与 model
    service = LLMFactory.create(provider="deepseek", api_key="test_key_stream")

    sse_chunks = [
        ": keep-alive ping\n\n",
        'data: {"choices":[{"delta":{}}]}\n\n',
        'data: {"choices":[{"delta":{"content":"Valid Chunk"}}]}\n\n',
        "data: invalid_json\n\n",
        "data: [DONE]\n\n",
    ]
    mock_stream_content = "".join(sse_chunks).encode("utf-8")

    with respx.mock:
        respx.post("https://api.deepseek.com/chat/completions").mock(
            return_value=Response(
                200,
                content=mock_stream_content,
                headers={"content-type": "text/event-stream"},
            )
        )

        collected_text = []
        async for chunk in service.generate_stream(prompt="Resilience Test"):
            collected_text.append(chunk)

        assert collected_text == ["Valid Chunk"]
