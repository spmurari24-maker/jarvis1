from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from jarvis.config import Settings
from jarvis.core.audit import AuditLogger
from jarvis.core.confirmation import ConfirmationManager
from jarvis.core.event_bus import EventBus
from jarvis.core.orchestrator import Orchestrator
from jarvis.core.permissions import PermissionDenied, PermissionManager
from jarvis.core.prompt_security import inspect_untrusted_content
from jarvis.core.rate_limiter import RateLimitExceeded, RateLimiter
from jarvis.core.shutdown import ShutdownController, SystemHalted
from jarvis.core.skill_registry import SkillRegistry, load_permission_ceilings
from jarvis.llm import LLMClient, ModelUnavailable
from jarvis.web_search import (WebSearchError, best_answer_excerpt, result_payload, search_web,
                               web_query_for_message)


class InvokeRequest(BaseModel):
    arguments: dict[str, Any] = Field(default_factory=dict)


class ConversationTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    search_web: bool | None = None
    history: list[ConversationTurn] = Field(default_factory=list, max_length=16)


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)


class ShutdownRequest(BaseModel):
    phrase: str = Field(min_length=1, max_length=100)


def create_app(project_dir: str | Path | None = None, settings: Settings | None = None) -> FastAPI:
    root = Path(project_dir or Path.cwd()).resolve()
    config = settings or Settings.load(root)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    registry = SkillRegistry()
    registry.discover(root / config.skills_dir)
    permission_path = root / "config" / "permissions.yaml"
    permissions = PermissionManager(load_permission_ceilings(permission_path))
    audit_path = Path(config.audit_path)
    if not audit_path.is_absolute():
        audit_path = root / audit_path
    audit = AuditLogger(audit_path)
    event_bus = EventBus()
    shutdown = ShutdownController()
    confirmations = ConfirmationManager(config.confirmation_ttl_seconds)
    orchestrator = Orchestrator(registry, permissions, confirmations, shutdown, audit, event_bus, config.offline_safe)
    model_client = LLMClient(config)
    limiter = RateLimiter(config.rate_limit_requests, config.rate_limit_window_seconds)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        audit.record("server_started", skills=[manifest.name for manifest in registry.list()], offline_safe=config.offline_safe)
        yield
        if not shutdown.halted:
            audit.record("server_stopped")

    app = FastAPI(title=config.app_name, version="0.1.0", lifespan=lifespan)
    app.state.orchestrator = orchestrator
    app.state.registry = registry
    app.state.settings = config
    app.state.model_client = model_client
    app.state.rate_limiter = limiter
    static_dir = Path(__file__).resolve().parent / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", include_in_schema=False)
    async def dashboard():
        return FileResponse(static_dir / "index.html")

    async def authorize_request(request: Request, x_api_key: str | None = Header(default=None)) -> None:
        if config.api_key and not hmac.compare_digest(x_api_key or "", config.api_key):
            raise HTTPException(status_code=401, detail="Invalid or missing API key")
        client = request.client.host if request.client else "unknown"
        try:
            await limiter.check(client)
        except RateLimitExceeded as exc:
            raise HTTPException(status_code=429, detail="Rate limit exceeded",
                                headers={"Retry-After": str(max(1, int(exc.retry_after)))}) from exc

    @app.exception_handler(PermissionDenied)
    async def permission_error(_: Request, exc: PermissionDenied):
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    @app.exception_handler(SystemHalted)
    async def halted_error(_: Request, exc: SystemHalted):
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.get("/health")
    async def health():
        model_status = await model_client.status()
        return {"status": "halted" if shutdown.halted else "ready", "offline_safe": config.offline_safe,
                "web_search_enabled": config.web_search_enabled, "llm": model_status}

    @app.get("/v1/skills", dependencies=[Depends(authorize_request)])
    async def list_skills():
        return [{"name": item.name, "description": item.description,
                 "permission": permissions.effective_tier(item).value,
                 "tools": [{"name": tool.name, "description": tool.description, "risk": tool.risk.value,
                            "required_tier": tool.required_tier.value, "critical_action": tool.critical_action}
                           for tool in item.tools]} for item in registry.list()]

    @app.post("/v1/chat", dependencies=[Depends(authorize_request)])
    async def chat(body: ChatRequest):
        shutdown.ensure_running()
        if body.search_web is not True and body.search_web is not False and _has_skill_intent(body.text, registry):
            return await orchestrator.route(body.text)
        query = None if body.search_web is False else web_query_for_message(body.text)
        if body.search_web is True and query is None:
            query = body.text[:500]
        results: list[Any] = []
        suspicious = False
        search_warning = ""
        if query:
            results, suspicious, search_warning = await fetch_web_results(query)
        task = asyncio.current_task()
        if task is not None:
            shutdown.register_task(task)
        try:
            answer, provider = await model_client.answer(
                body.text, [turn.model_dump() for turn in body.history], results
            )
            answer = _address_user(answer)
            shutdown.ensure_running()
            audit.record("chat_answered", provider=provider, web_search_used=bool(results),
                         history_turn_count=len(body.history))
            return {"status": "completed", "answer": answer, "spoken_answer": answer[:900],
                    "sources": [result_payload(item) for item in results], "provider": provider,
                    "web_search_used": bool(results), "external_content_warning": suspicious,
                    "search_warning": search_warning}
        except asyncio.CancelledError:
            raise
        except ModelUnavailable as exc:
            audit.record("chat_model_unavailable", web_search_used=bool(results))
            reason = str(exc)
            normalized_reason = reason.casefold()
            if "rejected the configured credentials" in normalized_reason:
                answer = ("Gemini rejected the current API key, sir. Create a free key in Google AI Studio, "
                          "replace GEMINI_API_KEY in this project's .env, then restart JARVIS.")
                safe_warning = "Check the free Gemini API key saved in the project .env file."
                status = "setup_required"
            elif "rate limited" in normalized_reason or "temporarily unavailable" in normalized_reason:
                answer = "I could not complete that answer just now, sir. Please try again in a moment."
                safe_warning = "Please try again in a moment."
                status = "model_unavailable"
            elif "could not be reached" in normalized_reason:
                answer = "I could not connect to the answer service, sir. Check your internet connection and try again."
                safe_warning = "Check your internet connection and try again."
                status = "model_unavailable"
            else:
                answer = ("I cannot answer conversational questions until a free Gemini API key is connected, sir. "
                          "Add GEMINI_API_KEY to .env, or start Ollama with the configured local model.")
                safe_warning = "Add a free Gemini API key or start Ollama."
                status = "setup_required"
            if results:
                excerpt = best_answer_excerpt(query or body.text, results)
                answer = f"{answer} The best search result says: {excerpt}"
                safe_warning = "Showing a search excerpt because JARVIS could not generate a full answer."
                status = "model_unavailable"
            return {"status": status, "answer": answer, "spoken_answer": answer[:900],
                    "sources": [result_payload(item) for item in results],
                    "provider": "search fallback" if results else "none", "web_search_used": bool(results),
                    "external_content_warning": suspicious, "search_warning": safe_warning}

    async def fetch_web_results(query: str) -> tuple[list[Any], bool, str]:
        if not config.web_search_enabled:
            return [], False, "Web search is disabled in local settings."
        query_hash = hashlib.sha256(query.casefold().encode("utf-8")).hexdigest()
        audit.record("web_search_requested", query_hash=query_hash, provider="DuckDuckGo")
        task = asyncio.current_task()
        if task is not None:
            shutdown.register_task(task)
        try:
            results = await search_web(query)
            shutdown.ensure_running()
        except asyncio.CancelledError:
            audit.record("web_search_cancelled", query_hash=query_hash, provider="DuckDuckGo")
            raise
        except WebSearchError:
            audit.record("web_search_failed", query_hash=query_hash, provider="DuckDuckGo",
                         error_type="WebSearchError")
            return [], False, "Web search is temporarily unreachable; answering from model knowledge."
        external = "\n".join(f"{item.title}\n{item.snippet}" for item in results)
        inspected = inspect_untrusted_content(external)
        audit.record("web_search_completed", query_hash=query_hash, provider="DuckDuckGo",
                     result_count=len(results), suspicious=inspected.suspicious)
        warning = "No web results found; answering from model knowledge." if not results else ""
        return results, inspected.suspicious, warning

    def _has_skill_intent(text: str, skills: SkillRegistry) -> bool:
        normalized = text.casefold()
        return any(phrase.casefold() in normalized
                   for manifest in skills.list() for phrase in manifest.intents)

    def _address_user(answer: str) -> str:
        return answer if re.search(r"\bsir\b", answer, flags=re.IGNORECASE) else f"Certainly, sir. {answer}"

    async def answer_from_web(query: str) -> dict[str, Any]:
        shutdown.ensure_running()
        results, suspicious, warning = await fetch_web_results(query)
        payload = [result_payload(item) for item in results]
        if not payload:
            status = "disabled" if not config.web_search_enabled else "unavailable" if warning.startswith("Web search") else "no_results"
            answer = "Web search is disabled in local settings, sir." if status == "disabled" else (
                warning or "I found no web results for that search, sir."
            )
            return {"status": status, "answer": answer, "spoken_answer": answer, "sources": []}
        excerpt = best_answer_excerpt(query, results)
        answer = f"Certainly, sir. {excerpt or payload[0]['title']}"
        return {"status": "completed", "answer": answer, "spoken_answer": answer[:600],
                "sources": payload, "external_content_warning": suspicious,
                "provider": "DuckDuckGo", "search_warning": warning}

    @app.post("/v1/search", dependencies=[Depends(authorize_request)])
    async def search(body: SearchRequest):
        query = body.query.strip()
        if not query:
            raise HTTPException(status_code=422, detail="query cannot be blank")
        return await answer_from_web(query)

    @app.post("/v1/skills/{skill_name}/{tool_name}", dependencies=[Depends(authorize_request)])
    async def invoke(skill_name: str, tool_name: str, body: InvokeRequest):
        try:
            return await orchestrator.invoke(skill_name, tool_name, body.arguments)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/v1/confirmations/{confirmation_id}", dependencies=[Depends(authorize_request)])
    async def approve(confirmation_id: str):
        try:
            return await orchestrator.confirm(confirmation_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/v1/shutdown", dependencies=[Depends(authorize_request)])
    async def shutdown_route(body: ShutdownRequest):
        try:
            return await orchestrator.shutdown_all(body.phrase)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return app




app = create_app()
