"""Remote AEGIS project worker: inspect, propose, safely apply, verify, and publish a PR."""
from __future__ import annotations
import argparse, json, os, subprocess
from pathlib import Path
from typing import Any

MAX_FILE_BYTES = 40_000
MAX_CONTEXT = 180_000
CAPABILITIES = {"terminal.inspect", "terminal.execute"}

def run(cmd: list[str], *, cwd: Path, timeout: int = 300) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=timeout, check=False)

def snapshot(project: Path) -> str:
    files = run(["git", "ls-files"], cwd=project).stdout.splitlines()
    chunks, total = [], 0
    for name in files:
        if total >= MAX_CONTEXT: break
        path = project / name
        if not path.is_file() or ".git" in path.parts: continue
        try: data = path.read_text(encoding="utf-8")[:MAX_FILE_BYTES]
        except (OSError, UnicodeDecodeError): continue
        chunks.append(f"\n--- {name} ---\n{data}")
        total += len(data)
    return "".join(chunks)

def deterministic_inspection(objective: str, context: str) -> str:
    """Produce a safe read-only report when no approved local model is reachable."""
    files = [line.removeprefix("--- ").removesuffix(" ---") for line in context.splitlines() if line.startswith("--- ") and line.endswith(" ---")]
    test_files = [name for name in files if name.startswith("tests/") and name.endswith(".py")]
    workflow_files = [name for name in files if name.startswith(".github/workflows/") and name.endswith((".yml", ".yaml"))]
    has_coverage = any(name in {"pyproject.toml", "pytest.ini", ".coveragerc", "setup.cfg"} for name in files)
    has_pytest = "pytest" in context.lower()
    findings = [
        f"Test discovery is concentrated in {len(test_files)} test files. Add an explicit coverage threshold and publish coverage artifacts so regressions are measurable.",
        f"The repository contains {len(workflow_files)} GitHub Actions workflow files. Add a dedicated test-matrix job for supported Python/runtime combinations and make it a required PR check.",
        (
            "The snapshot references pytest; standardize test execution and reporting around pytest with JUnit/coverage output."
            if has_pytest
            else
            "The snapshot does not show pytest configuration. Add a pytest-based test runner with JUnit/coverage output while retaining compatibility with the existing suite."
        ),
    ]
    if has_coverage:
        findings[0] = "Coverage-related configuration is present, but the test infrastructure should enforce a minimum threshold in CI and publish the report as a build artifact."
    return (
        "Deterministic read-only inspection fallback was used because no approved local model "
        "was available. No files were modified.\n\n"
        + "\n".join(f"{i}. {finding}" for i, finding in enumerate(findings, 1))
        + f"\n\nObjective: {objective}"
    )

def model_plan(objective: str, context: str, capability: str) -> dict[str, Any]:
    from jarvis.model_service import ModelRuntime
    if capability == "terminal.inspect":
        instruction = """Return JSON only with:
summary: string
report: string

The report must identify concrete repository findings relevant to the objective.
Do not propose or include a patch. Do not modify files."""
    else:
        instruction = """Return JSON only with:
summary: string
patch: string

The patch must be a unified git diff. Modify only files necessary for the objective.
Do not include shell commands, secrets, generated binaries, or files outside the repository.
If the objective cannot be safely implemented from the snapshot, return an empty patch and explain why."""
    prompt = f"""You are the AEGIS software agent.
Objective: {objective}
Capability: {capability}

Repository snapshot:
{context}

{instruction}"""
    result = ModelRuntime().chat(
        messages=[{"role": "user", "content": prompt}],
        purpose="coding" if capability == "terminal.execute" else "research",
        local_only=True, allow_external=False,
    )
    return json.loads(result["response"]["content"])

def issue_comment(issue: str, body: str) -> None:
    if not issue or "#" not in issue: return
    repo, number = issue.split("#", 1)
    result = subprocess.run(
        ["gh", "issue", "comment", number, "--repo", repo, "--body", body],
        text=True, capture_output=True, timeout=120, check=False,
    )
    if result.returncode:
        print(json.dumps({"stage": "issue_comment_failed", "error": result.stderr.strip()}))

def set_status(status: str) -> None:
    output = os.getenv("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as handle:
            handle.write(f"status={status}\n")

def apply_patch(project: Path, patch: str) -> None:
    if not patch.strip(): raise RuntimeError("coding agent returned no patch")
    check = run(["git", "apply", "--check", "--whitespace=error-all", "-"], cwd=project)
    if check.returncode: raise RuntimeError(f"patch validation failed: {check.stderr.strip()}")
    applied = subprocess.run(
        ["git", "apply", "--whitespace=error-all", "-"], cwd=project,
        input=patch, text=True, capture_output=True, timeout=120, check=False,
    )
    if applied.returncode: raise RuntimeError(f"patch application failed: {applied.stderr.strip()}")

def verify(project: Path) -> None:
    compile_result = run(["python3", "-m", "compileall", "-q", "."], cwd=project, timeout=300)
    if compile_result.returncode:
        raise RuntimeError(f"compile verification failed: {compile_result.stderr.strip()}")
    tests = run(["python3", "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"], cwd=project, timeout=600)
    if tests.returncode:
        raise RuntimeError(f"test verification failed: {tests.stdout[-6000:]}\n{tests.stderr[-3000:]}")

def publish(project: Path, job_id: str, objective: str) -> str:
    if not run(["git", "status", "--short"], cwd=project).stdout.strip():
        raise RuntimeError("coding agent produced no repository changes")
    branch = f"aegis/{job_id}"
    commands = [
        ["git", "checkout", "-b", branch],
        ["git", "add", "-A"],
        ["git", "-c", "user.name=AEGIS Worker", "-c", "user.email=aegis-worker@users.noreply.github.com",
         "commit", "-m", f"AEGIS: {objective[:60]}"],
    ]
    for cmd in commands:
        result = run(cmd, cwd=project, timeout=120)
        if result.returncode: raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    pushed = run(["git", "push", "-u", "origin", branch], cwd=project, timeout=300)
    if pushed.returncode: raise RuntimeError(pushed.stderr.strip() or pushed.stdout.strip())
    pr = run(["gh", "pr", "create", "--base", "master", "--head", branch,
              "--title", f"AEGIS: {objective[:80]}",
              "--body", f"Automated AEGIS implementation for job {job_id}.\n\nObjective: {objective}"],
             cwd=project, timeout=120)
    if pr.returncode: raise RuntimeError(pr.stderr.strip() or pr.stdout.strip())
    return pr.stdout.strip()

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--capability", required=True)
    parser.add_argument("--issue", required=True)
    parser.add_argument("--objective", required=True)
    args = parser.parse_args()
    if args.capability not in CAPABILITIES:
        raise RuntimeError(f"unsupported remote capability: {args.capability}")
    project = Path(args.project).resolve()
    if not (project / ".git").exists(): raise RuntimeError("target project is not a git checkout")
    print(json.dumps({"stage": "inspect", "job_id": args.job_id, "capability": args.capability}))
    context = snapshot(project)
    try:
        plan = model_plan(args.objective, context, args.capability)
    except LookupError as exc:
        if args.capability == "terminal.inspect":
            report = deterministic_inspection(args.objective, context)
            issue_comment(args.issue, f"## AEGIS inspection report\\n\\n**Job:** `{args.job_id}`\\n\\n{report}")
            set_status("passed")
            print(json.dumps({"stage": "reported", "job_id": args.job_id, "mode": "deterministic_fallback"}))
            return 0
        set_status("escalated")
        issue_comment(args.issue, f"AEGIS job `{args.job_id}` escalated: no approved local model is currently available. The worker will not use an external model.\\n\\nReason: `{exc}`")
        print(json.dumps({"stage": "escalated", "job_id": args.job_id, "reason": str(exc)}))
        return 0
    print(json.dumps({"stage": "plan", "summary": plan.get("summary", "")}))
    if args.capability == "terminal.inspect":
        report = str(plan.get("report", "")).strip()
        if not report: raise RuntimeError("inspection agent returned no report")
        issue_comment(args.issue, f"## AEGIS inspection report\n\n**Job:** `{args.job_id}`\n\n{report}")
        set_status("passed")
        print(json.dumps({"stage": "reported", "job_id": args.job_id}))
        return 0
    apply_patch(project, str(plan.get("patch", "")))
    verify(project)
    pr = publish(project, args.job_id, args.objective)
    set_status("passed")
    print(json.dumps({"stage": "published", "job_id": args.job_id, "pull_request": pr}))
    return 0

if __name__ == "__main__":
    try: raise SystemExit(main())
    except Exception as exc:
        set_status("failed")
        print(json.dumps({"stage": "failed", "error": str(exc)}))
        raise
