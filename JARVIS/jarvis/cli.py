from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from jarvis.config import Settings
from jarvis.core.audit import AuditLogger
from jarvis.core.confirmation import ConfirmationManager
from jarvis.core.event_bus import EventBus
from jarvis.core.orchestrator import Orchestrator
from jarvis.core.permissions import PermissionManager
from jarvis.core.shutdown import ShutdownController
from jarvis.core.skill_registry import SkillRegistry, load_permission_ceilings


def _build(root: Path):
    settings = Settings.load(root)
    registry = SkillRegistry()
    registry.discover(root / settings.skills_dir)
    permission_file = root / "config" / "permissions.yaml"
    audit_path = Path(settings.audit_path)
    if not audit_path.is_absolute():
        audit_path = root / audit_path
    return settings, registry, Orchestrator(
        registry, PermissionManager(load_permission_ceilings(permission_file)), ConfirmationManager(settings.confirmation_ttl_seconds),
        ShutdownController(), AuditLogger(audit_path), EventBus(), settings.offline_safe,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jarvis", description="JARVIS local foundation")
    parser.add_argument("--project-dir", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("serve", help="Start the local FastAPI service")
    sub.add_parser("skills", help="List discovered skills and tools")
    call = sub.add_parser("call", help="Call a skill tool")
    call.add_argument("skill")
    call.add_argument("tool")
    call.add_argument("--arguments", default="{}", help="Tool arguments as JSON")
    chat = sub.add_parser("chat", help="Route one request through the conservative intent router")
    chat.add_argument("text")
    return parser


async def _run(args: argparse.Namespace) -> int:
    root = args.project_dir.resolve()
    settings, registry, orchestrator = _build(root)
    if args.command == "skills":
        print(json.dumps([{"name": manifest.name, "permission": manifest.permission.value,
                           "tools": [tool.name for tool in manifest.tools]} for manifest in registry.list()], indent=2))
        return 0
    if args.command == "call":
        result = await orchestrator.invoke(args.skill, args.tool, json.loads(args.arguments))
    else:
        result = await orchestrator.route(args.text)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


def main() -> None:
    args = _parser().parse_args()
    if args.command == "serve":
        import uvicorn
        from jarvis.api import create_app
        root = args.project_dir.resolve()
        settings = Settings.load(root)
        uvicorn.run(create_app(root, settings), host=settings.host, port=settings.port, reload=False)
        return
    raise SystemExit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
