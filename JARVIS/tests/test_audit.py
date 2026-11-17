import json

from jarvis.core.audit import AuditLogger


def test_audit_records_json_and_redacts_secret_fields(tmp_path):
    path = tmp_path / "audit" / "events.jsonl"
    AuditLogger(path).record("example", api_key="secret-value", skill="demo")
    item = json.loads(path.read_text(encoding="utf-8"))
    assert item["event"] == "example"
    assert item["details"]["api_key"] == "[REDACTED]"
