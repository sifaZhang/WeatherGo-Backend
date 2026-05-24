import pytest
from unittest.mock import patch
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

# /health 测试
def test_health(client):
    response = client.get('/health')
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}

# /recommend 测试 - 缺少参数
def test_recommend_missing_params(client):
    response = client.post('/recommend', json={})
    assert response.status_code == 400
    assert "error" in response.get_json()

# /recommend 测试 - 位置无法识别
def test_recommend_invalid_location(client):
    with patch('app.get_coordinates', return_value=(None, None)):
        response = client.post('/recommend', json={
            "location": "xyzabc123",
            "activity_type": "cafe"
        })
        assert response.status_code == 404
        assert "error" in response.get_json()

# /recommend 测试 - 天气服务不可用
def test_recommend_weather_unavailable(client):
    with patch('app.get_coordinates', return_value=(-36.85, 174.76)):
        with patch('app.get_weather', return_value=None):
            response = client.post('/recommend', json={
                "location": "Auckland",
                "activity_type": "cafe"
            })
            assert response.status_code == 503
            assert "error" in response.get_json()

# /recommend 测试 - 附近没有相关地点
def test_recommend_no_places(client):
    with patch('app.get_coordinates', return_value=(-36.85, 174.76)):
        with patch('app.get_weather', return_value={"status": "sunny", "temperature": 18.0}):
            with patch('app.get_places', return_value=[]):
                response = client.post('/recommend', json={
                    "location": "Auckland",
                    "activity_type": "cafe"
                })
                assert response.status_code == 404
                assert "error" in response.get_json()

# /recommend 测试 - 成功返回
def test_recommend_success(client):
    with patch('app.get_coordinates', return_value=(-36.85, 174.76)):
        with patch('app.get_weather', return_value={"status": "sunny", "temperature": 18.0}):
            with patch('app.get_places', return_value=["Cafe One", "Cafe Two"]):
                with patch('app.get_recommendation', return_value="Great weather, go to Cafe One!"):
                    response = client.post('/recommend', json={
                        "location": "Auckland",
                        "activity_type": "cafe"
                    })
                    assert response.status_code == 200
                    data = response.get_json()
                    assert data["location"] == "Auckland"
                    assert data["weather"]["status"] == "sunny"
                    assert len(data["places"]) == 2
                    assert data["recommendation"] is not None