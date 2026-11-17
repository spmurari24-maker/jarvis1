import pytest

from jarvis.core.permissions import PermissionDenied, PermissionManager
from jarvis.models import PermissionTier


def test_critical_tool_requires_approval_even_for_autonomous_skill(core):
    demo = core.registry.get("demo").manifest
    tool = demo.tool("demo_critical_action")
    PermissionManager().authorize(demo, tool)
    assert PermissionManager().requires_confirmation(demo, tool)


def test_configured_ceiling_can_restrict_skill(core):
    demo = core.registry.get("demo").manifest
    tool = demo.tool("echo")
    with pytest.raises(PermissionDenied):
        PermissionManager({"demo": PermissionTier.OBSERVE}).authorize(demo, tool)


def test_approval_ceiling_requires_confirmation_for_low_risk_actions(core):
    demo = core.registry.get("demo").manifest
    permissions = PermissionManager({"demo": PermissionTier.ACT_WITH_APPROVAL})
    assert permissions.requires_confirmation(demo, demo.tool("echo"))
