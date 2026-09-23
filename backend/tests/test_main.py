from config import AppSettings


# ------------------------------------------------------------------
# 1. 系统基础路由测试
# ------------------------------------------------------------------


def test_root_endpoint(test_client):
    """验证根路径引导接口"""
    response = test_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert data["docs"] == "/docs"
    assert data["health"] == "/health"
    assert data["ready"] == "/ready"


def test_health_check_endpoint(test_client):
    """验证健康检查接口返回 200 OK"""
    response = test_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ------------------------------------------------------------------
# 2. CORS 跨域配置测试
# ------------------------------------------------------------------


def test_cors_preflight_headers(test_client):
    """验证 OPTIONS 预检请求包含正确的 CORS 响应头"""
    response = test_client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_origins_parsed_from_comma_separated_string():
    """逗号分隔的来源能被正确拆分，且空项被丢弃"""
    settings = AppSettings(CORS_ALLOW_ORIGINS="http://a.com, http://b.com ,")

    assert settings.cors_allow_origins == ["http://a.com", "http://b.com"]


# ------------------------------------------------------------------
# 3. 就绪探针测试
# ------------------------------------------------------------------


def test_ready_returns_ok_when_configured(test_client):
    """配置齐全时就绪探针返回 200，并列出可用提供商"""
    response = test_client.get("/ready")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "deepseek" in data["providers"]


def test_ready_warns_when_api_token_missing(test_client):
    """未配置 API_TOKEN 属于安全告警，但不影响就绪状态"""
    data = test_client.get("/ready").json()

    assert data["status"] == "ok"
    assert any("API_TOKEN" in w for w in data["warnings"])


def test_ready_reports_unavailable_when_provider_cannot_be_built(
    monkeypatch, test_client
):
    """
    提供商配置不全（例如缺密钥）时返回 503。
    这是部署最常见的失误，就绪探针必须能报出来。
    """
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")

    response = test_client.get("/ready")

    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "unavailable"
    assert any("API Key 未配置" in problem for problem in data["problems"])


# ------------------------------------------------------------------
# 4. LLM 提供商发现接口测试
# ------------------------------------------------------------------


def test_list_providers(test_client):
    """验证 discovery 接口返回已注册的提供商列表，供前端渲染选择菜单"""
    response = test_client.get("/api/providers")

    assert response.status_code == 200
    assert "deepseek" in response.json()["providers"]
