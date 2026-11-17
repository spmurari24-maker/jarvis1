from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from jarvis.core.event_bus import EventBus


class PermissionTier(str, Enum):
    OBSERVE = "observe"
    SUGGEST = "suggest"
    ACT_WITH_APPROVAL = "act-with-approval"
    ACT_AUTONOMOUSLY = "act-autonomously"

    @property
    def rank(self) -> int:
        return {
            PermissionTier.OBSERVE: 0,
            PermissionTier.SUGGEST: 1,
            PermissionTier.ACT_WITH_APPROVAL: 2,
            PermissionTier.ACT_AUTONOMOUSLY: 3,
        }[self]


class RiskLevel(str, Enum):
    LOW = "low"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class ToolManifest:
    name: str
    description: str
    risk: RiskLevel = RiskLevel.LOW
    required_tier: PermissionTier = PermissionTier.OBSERVE
    critical_action: bool = False


@dataclass(frozen=True)
class SkillManifest:
    name: str
    description: str
    permission: PermissionTier
    module: str
    class_name: str
    tools: tuple[ToolManifest, ...] = ()
    intents: dict[str, str] = field(default_factory=dict)

    def tool(self, name: str) -> ToolManifest:
        for tool in self.tools:
            if tool.name == name:
                return tool
        raise KeyError(f"Unknown tool '{name}' for skill '{self.name}'")


@dataclass
class ToolResult:
    ok: bool
    output: Any
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SkillContext:
    request_id: str
    offline_safe: bool
    event_bus: EventBus

