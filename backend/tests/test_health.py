def test_health_check_returns_200_and_ok(test_client):
    """
    测试用例：验证 GET /health 接口是否返回 200 状态码及 status=ok 响应内容
    """
    # 1. 向 /health 发起模拟请求
    response = test_client.get("/health")

    # 2. 检查响应 HTTP 状态码
    assert response.status_code == 200

    # 3. 检查响应数据结构与内容
    assert response.json() == {"status": "ok"}
