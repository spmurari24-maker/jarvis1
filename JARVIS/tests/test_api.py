from pathlib import Path

from fastapi.testclient import TestClient

from jarvis.api import create_app
from jarvis.config import Settings


def test_api_health_skill_listing_and_approval_flow(tmp_path: Path):
    project = Path(__file__).resolve().parents[1]
    settings = Settings(audit_path=str(tmp_path / "audit.jsonl"), skills_dir="skills")
    with TestClient(create_app(project, settings)) as client:
        home = client.get("/")
        assert home.status_code == 200
        assert "JARVIS" in home.text
        assert "Gemini" in home.text
        assert "Claude" not in home.text
        assert client.get("/static/styles.css").status_code == 200
        script = client.get("/static/app.js").text
        assert "sendCommand" in script
        assert "SpeechRecognition" in script
        assert "speechSynthesis.speak" in script
        assert client.get("/health").json()["web_search_enabled"] is True
        assert client.get("/health").json()["status"] == "ready"
        assert len(client.get("/v1/skills").json()) == 2
        pending = client.post("/v1/skills/demo/demo_critical_action", json={"arguments": {}}).json()
        assert pending["status"] == "confirmation_required"
        approved = client.post(f"/v1/confirmations/{pending['confirmation_id']}")
        assert approved.json()["status"] == "completed"


def test_api_key_protects_control_endpoints(tmp_path: Path):
    project = Path(__file__).resolve().parents[1]
    settings = Settings(api_key="local-test-key", audit_path=str(tmp_path / "audit.jsonl"))
    with TestClient(create_app(project, settings)) as client:
        assert client.get("/v1/skills").status_code == 401
        assert client.get("/v1/skills", headers={"X-API-Key": "local-test-key"}).status_code == 200


