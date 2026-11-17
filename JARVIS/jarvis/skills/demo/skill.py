from __future__ import annotations

import json
import re
from typing import Any

from jarvis.models import SkillContext, SkillManifest, ToolResult
from jarvis.skills.base import BaseSkill


class DemoSkill(BaseSkill):
    def __init__(self, manifest: SkillManifest):
        self.manifest = manifest

    async def execute(self, tool_name: str, arguments: dict[str, Any], context: SkillContext) -> ToolResult:
        if tool_name == "greet":
            return ToolResult(True, "At your service, sir.")
        if tool_name == "echo":
            value = arguments.get("text", "")
            if not isinstance(value, str) or len(value) > 4000:
                raise ValueError("text must be a string of at most 4000 characters")
            return ToolResult(True, value)
        if tool_name == "publish_event":
            event_name = arguments.get("event", "demo.message")
            payload = arguments.get("payload", {})
            if not isinstance(event_name, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", event_name):
                raise ValueError("event must be 1 to 80 letters, digits, dots, underscores, or hyphens")
            if not isinstance(payload, dict) or len(json.dumps(payload, default=str)) > 4000:
                raise ValueError("payload must be an object of at most 4000 characters")
            delivered = await context.event_bus.publish(event_name, payload)
            return ToolResult(True, {"event": event_name, "delivered": delivered})
        if tool_name == "demo_critical_action":
            return ToolResult(True, "Demo action completed; no external system was changed.")
        raise KeyError(f"Unknown demo tool: {tool_name}")
