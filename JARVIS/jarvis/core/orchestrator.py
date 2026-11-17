from __future__ import annotations

import asyncio
import secrets
from typing import Any

from jarvis.core.audit import AuditLogger
from jarvis.core.confirmation import ConfirmationManager
from jarvis.core.event_bus import EventBus
from jarvis.core.permissions import PermissionManager
from jarvis.core.prompt_security import wrap_untrusted_content
from jarvis.core.shutdown import ShutdownController
from jarvis.core.skill_registry import SkillRegistry
from jarvis.models import SkillContext, ToolResult


class Orchestrator:
    def __init__(self, registry: SkillRegistry, permissions: PermissionManager, confirmations: ConfirmationManager,
                 shutdown: ShutdownController, audit: AuditLogger, event_bus: EventBus, offline_safe: bool = True):
        self.registry = registry
        self.permissions = permissions
        self.confirmations = confirmations
        self.shutdown = shutdown
        self.audit = audit
        self.event_bus = event_bus
        self.offline_safe = offline_safe
        self._tasks: set[asyncio.Task] = set()

    def _check(self, skill_name: str, tool_name: str):
        self.shutdown.ensure_running()
        skill = self.registry.get(skill_name)
        tool = skill.manifest.tool(tool_name)
        self.permissions.authorize(skill.manifest, tool)
        return skill, tool

    async def invoke(self, skill_name: str, tool_name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        args = arguments or {}
        request_id = secrets.token_hex(12)
        try:
            skill, tool = self._check(skill_name, tool_name)
        except Exception as exc:
            self.audit.record("tool_denied", request_id=request_id, skill=skill_name, tool=tool_name,
                              error_type=type(exc).__name__)
            raise
        requires_confirmation = self.permissions.requires_confirmation(skill.manifest, tool)
        self.audit.record("tool_requested", request_id=request_id, skill=skill_name, tool=tool_name,
                          confirmation_required=requires_confirmation)
        if requires_confirmation:
            pending = self.confirmations.create(skill_name, tool_name, args, f"Run {skill_name}.{tool_name}?")
            self.audit.record("confirmation_requested", request_id=request_id, skill=skill_name, tool=tool_name)
            return {"status": "confirmation_required", "confirmation_id": pending.confirmation_id,
                    "summary": pending.summary, "expires_in_seconds": self.confirmations.ttl_seconds}
        return await self._execute(skill_name, tool_name, args, request_id)

    async def confirm(self, confirmation_id: str) -> dict[str, Any]:
        self.shutdown.ensure_running()
        pending = self.confirmations.consume(confirmation_id)
        self._check(pending.skill_name, pending.tool_name)
        request_id = secrets.token_hex(12)
        self.audit.record("confirmation_approved", request_id=request_id, skill=pending.skill_name, tool=pending.tool_name)
        return await self._execute(pending.skill_name, pending.tool_name, pending.arguments, request_id)

    async def _execute(self, skill_name: str, tool_name: str, arguments: dict[str, Any], request_id: str) -> dict[str, Any]:
        self.shutdown.ensure_running()
        skill = self.registry.get(skill_name)
        self.audit.record("tool_started", request_id=request_id, skill=skill_name, tool=tool_name)
        await self.event_bus.publish("tool.started", {"request_id": request_id, "skill": skill_name, "tool": tool_name})
        task = asyncio.current_task()
        if task:
            self._tasks.add(task)
            self.shutdown.register_task(task)
        try:
            result: ToolResult = await skill.execute(
                tool_name, arguments, SkillContext(request_id, self.offline_safe, self.event_bus)
            )
            self.audit.record("tool_completed", request_id=request_id, skill=skill_name, tool=tool_name, ok=result.ok)
            await self.event_bus.publish("tool.completed", {"request_id": request_id, "skill": skill_name,
                                                              "tool": tool_name, "ok": result.ok})
            return {"status": "completed", "request_id": request_id, "ok": result.ok,
                    "output": result.output, "metadata": result.metadata}
        except asyncio.CancelledError:
            self.audit.record("tool_cancelled", request_id=request_id, skill=skill_name, tool=tool_name)
            raise
        except Exception as exc:
            self.audit.record("tool_failed", request_id=request_id, skill=skill_name, tool=tool_name,
                              error_type=type(exc).__name__)
            raise
        finally:
            if task:
                self._tasks.discard(task)

    async def route(self, user_text: str) -> dict[str, Any]:
        """Conservative keyword router; it does not call an LLM or execute free-form plans."""
        self.shutdown.ensure_running()
        normalized = user_text.casefold()
        for manifest in self.registry.list():
            for phrase, tool_name in manifest.intents.items():
                if phrase.casefold() in normalized:
                    arguments: dict[str, Any] = {"text": user_text} if tool_name == "echo" else {}
                    return await self.invoke(manifest.name, tool_name, arguments)
        inspected = wrap_untrusted_content(user_text)
        self.audit.record("request_unmatched", suspicious=inspected.suspicious)
        return {"status": "unmatched", "message": "I could not map that request to a configured skill, sir.",
                "external_content_warning": inspected.suspicious}

    async def shutdown_all(self, phrase: str) -> dict[str, Any]:
        count = await self.shutdown.trigger(phrase)
        pending = self.confirmations.clear()
        self.audit.record("system_shutdown", cancelled_tasks=count, cleared_confirmations=pending)
        await self.event_bus.publish("system.shutdown", {"cancelled_tasks": count})
        return {"status": "halted", "cancelled_tasks": count, "cleared_confirmations": pending}
