from __future__ import annotations

from datetime import datetime
from typing import Any

from jarvis.models import SkillContext, SkillManifest, ToolResult
from jarvis.skills.base import BaseSkill


class SystemSkill(BaseSkill):
    def __init__(self, manifest: SkillManifest):
        self.manifest = manifest

    async def execute(self, tool_name: str, arguments: dict[str, Any], context: SkillContext) -> ToolResult:
        if tool_name == "status":
            return ToolResult(True, {"status": "ready", "offline_safe": context.offline_safe})
        if tool_name == "time":
            return ToolResult(True, datetime.now().astimezone().isoformat())
        raise KeyError(f"Unknown system tool: {tool_name}")
