from pathlib import Path

import pytest

from jarvis.core.audit import AuditLogger
from jarvis.core.confirmation import ConfirmationManager
from jarvis.core.event_bus import EventBus
from jarvis.core.orchestrator import Orchestrator
from jarvis.core.permissions import PermissionManager
from jarvis.core.shutdown import ShutdownController
from jarvis.core.skill_registry import SkillRegistry


@pytest.fixture
def core(tmp_path: Path):
    project = Path(__file__).resolve().parents[1]
    registry = SkillRegistry()
    registry.discover(project / "skills")
    return Orchestrator(registry, PermissionManager(), ConfirmationManager(60), ShutdownController(),
                        AuditLogger(tmp_path / "audit.jsonl"), EventBus(), offline_safe=True)
