from __future__ import annotations

from jarvis.models import PermissionTier, RiskLevel, SkillManifest, ToolManifest

_ALWAYS_CONFIRM_WORDS = ("purchase", "delete", "unlock", "send", "trade")


class PermissionDenied(PermissionError):
    pass


class PermissionManager:
    def __init__(self, ceilings: dict[str, PermissionTier] | None = None):
        self.ceilings = ceilings or {}

    def effective_tier(self, manifest: SkillManifest) -> PermissionTier:
        ceiling = self.ceilings.get(manifest.name, manifest.permission)
        return manifest.permission if manifest.permission.rank < ceiling.rank else ceiling

    def authorize(self, manifest: SkillManifest, tool: ToolManifest) -> None:
        tier = self.effective_tier(manifest)
        if tier.rank < tool.required_tier.rank:
            raise PermissionDenied(f"Skill '{manifest.name}' is limited to '{tier.value}', but '{tool.name}' requires '{tool.required_tier.value}'.")

    def requires_confirmation(self, manifest: SkillManifest, tool: ToolManifest) -> bool:
        tier = self.effective_tier(manifest)
        name = f"{manifest.name}.{tool.name}".lower()
        always_confirm = tool.critical_action or tool.risk in {RiskLevel.HIGH, RiskLevel.CRITICAL}
        always_confirm = always_confirm or any(word in name for word in _ALWAYS_CONFIRM_WORDS)
        if always_confirm:
            return True
        if tier in {PermissionTier.OBSERVE, PermissionTier.SUGGEST}:
            return False
        return tier == PermissionTier.ACT_WITH_APPROVAL
