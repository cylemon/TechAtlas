import json

import respx
from httpx import Response
from routers.deps import get_app_settings

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
PAYLOAD = {"query": "Quantum Computing Fundamentals", "provider": "deepseek"}

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


def _enable_auth(monkeypatch, token: str = "secret-token") -> None:
    """把 API_TOKEN 注入环境并刷新缓存（覆盖 conftest 里默认的关闭状态）"""
    monkeypatch.setenv("API_TOKEN", token)
    get_app_settings.cache_clear()


def _mock_llm() -> None:
    respx.post(DEEPSEEK_URL).mock(
        return_value=Response(
            200,
            json={
                "choices": [
                    {"message": {"content": json.dumps(ATLAS, ensure_ascii=False)}}
                ],
                "model": "deepseek-chat",
            },
        )
    )


def test_generate_requires_token_when_configured(monkeypatch, test_client):
    """配置了 API_TOKEN 后，不带令牌的生成请求必须被拒绝"""
    _enable_auth(monkeypatch)

    response = test_client.post("/api/generate", json=PAYLOAD)

    assert response.status_code == 401
    assert "X-API-Key" in response.json()["detail"]


def test_generate_rejects_wrong_token(monkeypatch, test_client):
    _enable_auth(monkeypatch)

    response = test_client.post(
        "/api/generate", json=PAYLOAD, headers={"X-API-Key": "wrong-token"}
    )

    assert response.status_code == 401


def test_stream_requires_token(monkeypatch, test_client):
    """流式端点与普通端点同属一个路由组，鉴权同样前置"""
    _enable_auth(monkeypatch)

    response = test_client.post("/api/generate/stream", json=PAYLOAD)

    assert response.status_code == 401


def test_generate_accepts_correct_token(monkeypatch, test_client):
    _enable_auth(monkeypatch)

    with respx.mock:
        _mock_llm()
        response = test_client.post(
            "/api/generate", json=PAYLOAD, headers={"X-API-Key": "secret-token"}
        )

    assert response.status_code == 200
    assert response.json()["topic"] == "Quantum Computing"


def test_generate_is_open_when_token_unset(test_client):
    """未配置 API_TOKEN 时放行（本地开发模式，启动时会打印告警）"""
    with respx.mock:
        _mock_llm()
        response = test_client.post("/api/generate", json=PAYLOAD)

    assert response.status_code == 200


def test_providers_endpoint_stays_public(monkeypatch, test_client):
    """厂商发现接口不产生任何费用，保持开放以便前端启动时拉取菜单"""
    _enable_auth(monkeypatch)

    assert test_client.get("/api/providers").status_code == 200
