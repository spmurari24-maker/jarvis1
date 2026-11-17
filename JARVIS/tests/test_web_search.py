from pathlib import Path

from fastapi.testclient import TestClient

from jarvis.api import create_app
from jarvis.config import Settings
from jarvis.web_search import SearchResult, _parse_results, _result_url, best_answer_excerpt, web_query_for_message


def test_parses_search_results_and_unwraps_provider_redirects():
    page = """
    <div class="result">
      <a class="result__a" href="/l/?uddg=https%3A%2F%2Fexample.com%2Farticle%3Fx%3D1%23part">Example result</a>
      <a class="result__snippet">A useful &amp; current summary.</a>
    </div>
    """
    results = _parse_results(page, 5)
    assert results == [SearchResult("Example result", "https://example.com/article?x=1", "A useful & current summary.")]
    assert _result_url("javascript:alert(1)") == ""


def test_detects_questions_and_explicit_search_commands():
    assert web_query_for_message("What is the capital of France?") is None
    assert web_query_for_message("What is the latest weather in Delhi today?") == "What is the latest weather in Delhi today?"
    assert web_query_for_message("search the web for local weather") == "local weather"
    assert web_query_for_message("hello Jarvis") is None


def test_answer_excerpt_prefers_a_short_relevant_sentence():
    results = [
        SearchResult("Paris", "https://example.com/paris", "Paris, France is a large city. Other unrelated details follow."),
        SearchResult("Capital of France", "https://example.com/capitals", "The capital of France has been Paris since 1944."),
    ]
    assert best_answer_excerpt("What is the capital of France?", results) == "The capital of France has been Paris since 1944."


def test_question_returns_answer_and_safe_source_links(monkeypatch, tmp_path: Path):
    async def fake_search(query: str):
        assert query == "What is the capital of France?"
        return [SearchResult("Paris", "https://example.com/paris", "Paris is the capital and largest city of France.")]

    monkeypatch.setattr("jarvis.api.search_web", fake_search)
    project = Path(__file__).resolve().parents[1]
    settings = Settings(audit_path=str(tmp_path / "audit.jsonl"), web_search_enabled=True)
    with TestClient(create_app(project, settings)) as client:
        health = client.get("/health").json()
        response = client.post("/v1/chat", json={"text": "What is the capital of France?", "search_web": True})
    assert health["web_search_enabled"] is True
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "model_unavailable"
    assert "sir" in payload["answer"]
    assert payload["sources"][0]["url"] == "https://example.com/paris"
    audit = (tmp_path / "audit.jsonl").read_text(encoding="utf-8")
    assert "web_search_completed" in audit
    assert "What is the capital of France?" not in audit


def test_explicit_web_search_endpoint_and_disabled_configuration(monkeypatch, tmp_path: Path):
    async def fake_search(query: str):
        return [SearchResult("Result", "https://example.com/", f"Found {query}.")]

    monkeypatch.setattr("jarvis.api.search_web", fake_search)
    project = Path(__file__).resolve().parents[1]
    with TestClient(create_app(project, Settings(audit_path=str(tmp_path / "enabled.jsonl")))) as client:
        response = client.post("/v1/search", json={"query": "test question"})
        assert response.status_code == 200
        assert response.json()["answer"].startswith("Certainly, sir.")
    with TestClient(create_app(project, Settings(audit_path=str(tmp_path / "disabled.jsonl"), web_search_enabled=False))) as client:
        response = client.post("/v1/search", json={"query": "Who is Ada Lovelace?"})
        assert response.status_code == 200
        assert response.json()["status"] == "disabled"
        assert "sir" in response.json()["answer"]
