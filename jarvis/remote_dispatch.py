"""Remote GitHub issue dispatcher for governed AEGIS project jobs."""
from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any


class RemoteDispatchError(RuntimeError):
    pass


def submit_issue(*, repository: str, objective: str, ref: str, capability: str,
                 job_id: str) -> dict[str, Any]:
    """Create an owner-authored AEGIS job issue using the authenticated gh CLI.

    The issue contains structured data only; it never accepts an arbitrary shell
    command from the operator request.
    """
    if not shutil.which("gh"):
        raise RemoteDispatchError("GitHub CLI 'gh' is required for remote dispatch")
    if not repository or "/" not in repository:
        raise RemoteDispatchError("repository must be owner/name")
    if not objective.strip():
        raise RemoteDispatchError("objective is required")
    body = "\n".join([
        "## AEGIS Remote Job",
        "",
        f"job_id: {job_id}",
        f"repository: {repository}",
        f"ref: {ref}",
        f"capability: {capability}",
        "",
        "### Objective",
        objective.strip(),
        "",
        "AEGIS owns this job. Do not edit the structured fields manually.",
    ])
    title = f"[AEGIS JOB] {objective.strip()[:100]}"
    proc = subprocess.run(
        ["gh", "issue", "create", "--repo", repository, "--title", title,
         "--body", body],
        capture_output=True, text=True, timeout=30, check=False,
    )
    if proc.returncode != 0:
        raise RemoteDispatchError(proc.stderr.strip() or "gh issue create failed")
    url = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""
    return {"repository": repository, "url": url, "title": title, "job_id": job_id}
