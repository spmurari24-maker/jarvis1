from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from jarvis.models import SkillContext, SkillManifest, ToolResult


class BaseSkill(ABC):
    manifest: SkillManifest

    @abstractmethod
    async def execute(self, tool_name: str, arguments: dict[str, Any], context: SkillContext) -> ToolResult:
        """Execute a declared tool. Implementations must validate their own arguments."""
