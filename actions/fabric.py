"""Small, auditable action fabric used by AEGIS agents.

The fabric is deliberately allow-listed. Higher-risk actions are admitted only
through explicit safety controls and policy.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import subprocess
from typing import Any, Callable


class ActionError(ValueError):
    """Raised when an action is invalid or not admitted."""


@dataclass(frozen=True)
class ActionContext:
    task_id: str
    workspace: Path
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ActionResult:
    action: str
    status: str
    output: dict[str, Any] = field(default_factory=dict)


Handler = Callable[[ActionContext, dict[str, Any]], dict[str, Any]]


class ActionFabric:
    """Resolve and execute explicitly registered actions."""

    def __init__(self, *, handlers: dict[str, Handler] | None = None):
        self._handlers = dict(handlers or {})

    def register(self, action: str, handler: Handler) -> None:
        if not action or "." not in action:
            raise ActionError("action id must be namespaced, e.g. filesystem.write")
        if action in self._handlers:
            raise ActionError(f"action already registered: {action}")
        self._handlers[action] = handler

    def available(self) -> list[str]:
        return sorted(self._handlers)

    def execute(self, action: str, args: dict[str, Any], context: ActionContext) -> ActionResult:
        handler = self._handlers.get(action)
        if handler is None:
            raise ActionError(f"action not admitted: {action}")
        result = handler(context, args)
        return ActionResult(action=action, status="passed", output=result)


def _safe_path(root: Path, relative: str) -> Path:
    if not relative or Path(relative).is_absolute():
        raise ActionError("path must be a non-empty relative path")
    target = (root / relative).resolve()
    root = root.resolve()
    if target != root and root not in target.parents:
        raise ActionError("path escapes workspace")
    return target


def filesystem_write(context: ActionContext, args: dict[str, Any]) -> dict[str, Any]:
    target = _safe_path(context.workspace, str(args.get("path", "")))
    content = args.get("content")
    if not isinstance(content, str):
        raise ActionError("content must be a string")
    if len(content.encode("utf-8")) > 1_000_000:
        raise ActionError("content exceeds 1 MB action limit")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return {"path": str(target.relative_to(context.workspace.resolve())), "bytes": len(content.encode("utf-8"))}


def filesystem_read(context: ActionContext, args: dict[str, Any]) -> dict[str, Any]:
    target = _safe_path(context.workspace, str(args.get("path", "")))
    if not target.is_file():
        raise ActionError("target is not a file")
    content = target.read_text(encoding="utf-8")
    if len(content.encode("utf-8")) > 1_000_000:
        raise ActionError("file exceeds 1 MB action limit")
    return {"path": str(target.relative_to(context.workspace.resolve())), "content": content}


def shell_execute(context: ActionContext, args: dict[str, Any]) -> dict[str, Any]:
    """Execute a terminal command after the shell safety gate is admitted.

    The command runs as the local user in the AEGIS workspace. The dispatcher
    is responsible for policy and safety admission before this action is called.
    """
    command = args.get("command")
    if not isinstance(command, str) or not command.strip():
        raise ActionError("command is required")
    timeout = int(args.get("timeout", 120))
    if timeout < 1 or timeout > 600:
        raise ActionError("timeout must be between 1 and 600 seconds")
    proc = subprocess.run(
        command,
        shell=True,
        cwd=context.workspace,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=os.environ.copy(),
    )
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout[-20000:],
        "stderr": proc.stderr[-20000:],
    }


def default_fabric() -> ActionFabric:
    from .website import website_create

    fabric = ActionFabric()
    fabric.register("filesystem.read", filesystem_read)
    fabric.register("filesystem.write", filesystem_write)
    fabric.register("website.create", website_create)
    fabric.register("shell.execute", shell_execute)
    return fabric
