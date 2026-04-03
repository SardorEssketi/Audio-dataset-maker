from fastapi.testclient import TestClient


def test_spa_fallback_pipeline_run_serves_index_html():
    # Import inside test to avoid side effects at collection time.
    from backend.app import app

    client = TestClient(app)
    r = client.get("/pipeline/run")
    assert r.status_code == 200
    # The built frontend index.html contains the root element and title.
    assert 'id="root"' in r.text


def test_api_config_exists_and_requires_auth():
    from backend.app import app

    client = TestClient(app)
    r = client.get("/api/config")
    # If route is missing we'd get 404; we want 401 for unauthenticated access.
    assert r.status_code == 401


def test_api_pipelines_exists_and_requires_auth():
    from backend.app import app

    client = TestClient(app)
    r = client.get("/api/pipelines")
    assert r.status_code == 401
