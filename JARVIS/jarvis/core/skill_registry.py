from __future__ import annotations

import importlib
from pathlib import Path
from typing import Type

import yaml

from jarvis.models import PermissionTier, RiskLevel, SkillManifest, ToolManifest
from jarvis.skills.base import BaseSkill


def _manifest_from_file(path: Path) -> SkillManifest:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Skill manifest must be a YAML mapping: {path}")
    tools = tuple(ToolManifest(name=item["name"], description=item.get("description", ""),
                               risk=RiskLevel(item.get("risk", "low")),
                               required_tier=PermissionTier(item.get("required_tier", "observe")),
                               critical_action=bool(item.get("critical_action", False)))
                  for item in raw.get("tools", []))
    manifest = SkillManifest(name=raw["name"], description=raw.get("description", ""),
                             permission=PermissionTier(raw.get("permission", "observe")),
                             module=raw["module"], class_name=raw["class_name"], tools=tools,
                             intents=raw.get("intents", {}))
    if not manifest.name.isidentifier() or len({tool.name for tool in tools}) != len(tools):
        raise ValueError(f"Invalid or duplicate skill/tool name in manifest: {path}")
    return manifest


class SkillRegistry:
    def __init__(self):
        self.skills: dict[str, BaseSkill] = {}

    def register(self, skill: BaseSkill) -> None:
        manifest = skill.manifest
        if manifest.name in self.skills:
            raise ValueError(f"Skill already registered: {manifest.name}")
        if not manifest.tools:
            raise ValueError(f"Skill '{manifest.name}' must declare at least one tool")
        self.skills[manifest.name] = skill

    def discover(self, skills_dir: str | Path) -> list[str]:
        """Load trusted Python skills described by manifests under the configured directory."""
        loaded: list[str] = []
        root = Path(skills_dir)
        packaged_skills = Path(__file__).resolve().parents[1] / "skills"
        if not root.exists() and packaged_skills.exists():
            root = packaged_skills
        for manifest_path in sorted(root.glob("**/manifest.yaml")):
            manifest = _manifest_from_file(manifest_path)
            module = importlib.import_module(manifest.module)
            skill_class: Type[BaseSkill] = getattr(module, manifest.class_name)
            instance = skill_class(manifest)
            if not isinstance(instance, BaseSkill):
                raise TypeError(f"{manifest.module}.{manifest.class_name} must extend BaseSkill")
            self.register(instance)
            loaded.append(manifest.name)
        return loaded

    def get(self, name: str) -> BaseSkill:
        return self.skills[name]

    def list(self) -> list[SkillManifest]:
        return [skill.manifest for skill in self.skills.values()]


def load_permission_ceilings(path: str | Path) -> dict[str, PermissionTier]:
    config_path = Path(path)
    if not config_path.exists():
        return {}
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict) or not isinstance(raw.get("skills", {}), dict):
        raise ValueError("Permission config must contain a 'skills' mapping")
    return {name: PermissionTier(item["tier"]) for name, item in raw.get("skills", {}).items()}
