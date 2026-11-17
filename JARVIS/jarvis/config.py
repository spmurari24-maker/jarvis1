from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


def _read_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


@dataclass(frozen=True)
class Settings:
    app_name: str = "JARVIS"
    host: str = "127.0.0.1"
    port: int = 8765
    offline_safe: bool = False
    web_search_enabled: bool = True
    llm_enabled: bool = True
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "gemma4"
    llm_timeout_seconds: int = 25
    rate_limit_requests: int = 30
    rate_limit_window_seconds: int = 60
    confirmation_ttl_seconds: int = 180
    audit_path: str = "storage/audit/events.jsonl"
    skills_dir: str = "skills"
    api_key: str = ""
    encryption_key: str = ""

    @classmethod
    def load(cls, project_dir: Path | None = None) -> "Settings":
        root = project_dir or Path.cwd()
        yaml_path = root / "config" / "settings.yaml"
        raw: dict[str, Any] = {}
        if yaml_path.exists():
            parsed = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
            if not isinstance(parsed, dict):
                raise ValueError("config/settings.yaml must contain a YAML mapping")
            raw.update(parsed)
        dotenv = _read_dotenv(root / ".env")
        env = {**dotenv, **os.environ}
        # A non-empty project key wins over a system-wide key so this app can be
        # configured without changing unrelated Windows environment settings.
        if dotenv.get("GEMINI_API_KEY", "").strip():
            env["GEMINI_API_KEY"] = dotenv["GEMINI_API_KEY"]
        mapping = {
            "host": "JARVIS_HOST", "port": "JARVIS_PORT", "offline_safe": "JARVIS_OFFLINE_SAFE",
            "web_search_enabled": "JARVIS_WEB_SEARCH_ENABLED",
            "llm_enabled": "JARVIS_LLM_ENABLED", "gemini_api_key": "GEMINI_API_KEY",
            "gemini_model": "JARVIS_GEMINI_MODEL", "ollama_url": "JARVIS_OLLAMA_URL",
            "ollama_model": "JARVIS_OLLAMA_MODEL", "llm_timeout_seconds": "JARVIS_LLM_TIMEOUT_SECONDS",
            "audit_path": "JARVIS_AUDIT_PATH", "api_key": "JARVIS_API_KEY",
            "encryption_key": "JARVIS_ENCRYPTION_KEY",
            "rate_limit_requests": "JARVIS_RATE_LIMIT_REQUESTS",
        }
        for field, variable in mapping.items():
            if variable in env:
                raw[field] = env[variable]
        bool_fields = {"offline_safe", "web_search_enabled", "llm_enabled"}
        int_fields = {"port", "rate_limit_requests", "rate_limit_window_seconds", "confirmation_ttl_seconds",
                      "llm_timeout_seconds"}
        allowed = set(cls.__dataclass_fields__)
        clean: dict[str, Any] = {}
        for key, value in raw.items():
            if key not in allowed:
                continue
            if key in bool_fields and isinstance(value, str):
                value = value.strip().lower() in {"1", "true", "yes", "on"}
            if key in int_fields:
                value = int(value)
            clean[key] = value
        settings = cls(**clean)
        if not (1 <= settings.port <= 65535):
            raise ValueError("port must be between 1 and 65535")
        if settings.rate_limit_requests < 1 or settings.rate_limit_window_seconds < 1:
            raise ValueError("rate limit values must be positive")
        if settings.llm_timeout_seconds < 1:
            raise ValueError("llm_timeout_seconds must be positive")
        return settings
