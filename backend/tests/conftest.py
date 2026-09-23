import pytest
from fastapi.testclient import TestClient
from main import app
from routers.deps import get_app_settings


@pytest.fixture
def test_client():
    """
    提供一个用于模拟前端发起 HTTP 请求的 FastAPI 测试客户端
    """
    return TestClient(app)


@pytest.fixture(autouse=True)
def _open_api_token(monkeypatch):
    """
    默认关闭鉴权，让用例不受开发者本地 .env 的影响（否则本机配了 API_TOKEN
    就会让所有生成接口的用例集体 401）。鉴权行为由 test_auth.py 专门覆盖。
    """
    monkeypatch.setenv("API_TOKEN", "")
    get_app_settings.cache_clear()
    yield
    get_app_settings.cache_clear()
