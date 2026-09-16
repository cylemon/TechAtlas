import pytest
from fastapi.testclient import TestClient
from main import app


@pytest.fixture
def test_client():
    """
    提供一个用于模拟前端发起 HTTP 请求的 FastAPI 测试客户端
    """
    return TestClient(app)
