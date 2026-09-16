def test_valid_stem_query(test_client):
    """测试用例 1：合法的科技课题应该被放行"""
    response = test_client.post("/api/generate", json={"query": "AI Agent 演进架构"})
    assert response.status_code == 200
    data = response.json()
    assert data["is_valid_domain"] is True
    assert data["reject_reason"] is None


def test_invalid_non_stem_query(test_client):
    """测试用例 2：非科技课题（如美食）应该被拦截"""
    response = test_client.post("/api/generate", json={"query": "推荐几款汉堡美食配方"})
    assert response.status_code == 200
    data = response.json()
    assert data["is_valid_domain"] is False
    assert "STEM" in data["reject_reason"]
