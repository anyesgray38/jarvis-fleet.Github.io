"""Remote AEGIS project worker: inspect, propose, safely apply, verify, and publish a PR."""
from __future__ import annotations
import argparse, json, re, subprocess
from pathlib import Path
from typing import Any

MAX_FILE_BYTES=40_000
MAX_CONTEXT=180_000
MAX_OBJECTIVE=8_000
ALLOWED_CAPABILITIES={"terminal.execute"}
PROTECTED_PREFIXES=(".git/", ".github/workflows/", "actions-runner/")
PROTECTED_NAMES={".env", ".env.example", "credentials", "credentials.json"}

def run(cmd:list[str],*,cwd:Path,timeout:int=300)->subprocess.CompletedProcess[str]:
    return subprocess.run(cmd,cwd=cwd,text=True,capture_output=True,timeout=timeout,check=False)

def snapshot(project:Path)->str:
    files=run(["git","ls-files"],cwd=project).stdout.splitlines()
    chunks=[]; total=0
    for name in files:
        if total>=MAX_CONTEXT: break
        path=project/name
        if not path.is_file() or ".git" in path.parts: continue
        try: data=path.read_text(encoding="utf-8")
        except (OSError,UnicodeDecodeError): continue
        data=data[:MAX_FILE_BYTES]
        chunks.append(f"\n--- {name} ---\n{data}")
        total+=len(data)
    return "".join(chunks)

def model_plan(objective:str,context:str)->dict[str,Any]:
    from jarvis.model_service import ModelRuntime
    prompt=f"""You are the AEGIS coding agent.
Objective: {objective}

Repository snapshot:
{context}

Return JSON only with:
summary: string
patch: string

The patch must be a unified git diff. Modify only files necessary for the objective.
Do not include shell commands, secrets, generated binaries, or files outside the repository.
If the objective cannot be safely implemented from the snapshot, return an empty patch and explain why."""
    result=ModelRuntime().chat(messages=[{"role":"user","content":prompt}],purpose="coding",
                               local_only=True,allow_external=False)
    content=result.get("response",{}).get("content") if isinstance(result,dict) else None
    if not isinstance(content,str):
        raise RuntimeError("coding agent returned no plan content")
    try:
        plan=json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError("coding agent returned invalid JSON") from exc
    if not isinstance(plan,dict) or not isinstance(plan.get("summary"),str) or not isinstance(plan.get("patch"),str):
        raise RuntimeError("coding agent plan must contain string summary and patch fields")
    return plan

def _patch_paths(patch:str)->set[str]:
    paths:set[str]=set()
    for line in patch.splitlines():
        if not line.startswith("diff --git "):
            continue
        match=re.match(r"^diff --git a/(.+) b/(.+)$",line)
        if not match:
            raise RuntimeError("patch contains an invalid file header")
        paths.update(match.groups())
    if not paths:
        raise RuntimeError("patch contains no file paths")
    return paths

def validate_patch(patch:str)->None:
    if "GIT binary patch" in patch or "Binary files " in patch:
        raise RuntimeError("binary patches are not permitted")
    for path in _patch_paths(patch):
        normalized=path.replace("\\","/")
        parts=Path(normalized).parts
        if Path(normalized).is_absolute() or ".." in parts:
            raise RuntimeError(f"patch path escapes the project: {path}")
        if normalized.startswith(PROTECTED_PREFIXES) or Path(normalized).name in PROTECTED_NAMES:
            raise RuntimeError(f"patch targets a protected path: {path}")

def ensure_clean(project:Path)->None:
    status=run(["git","status","--porcelain"],cwd=project)
    if status.returncode:
        raise RuntimeError(status.stderr.strip() or "unable to inspect project status")
    if status.stdout.strip():
        raise RuntimeError("target project checkout must be clean before AEGIS applies a patch")

def apply_patch(project:Path,patch:str)->None:
    if not patch.strip(): raise RuntimeError("coding agent returned no patch")
    validate_patch(patch)
    check=run(["git","apply","--check","--whitespace=error-all","-"],cwd=project)
    if check.returncode: raise RuntimeError(f"patch validation failed: {check.stderr.strip()}")
    applied=subprocess.run(["git","apply","--whitespace=error-all","-"],cwd=project,input=patch,
                           text=True,capture_output=True,timeout=120,check=False)
    if applied.returncode: raise RuntimeError(f"patch application failed: {applied.stderr.strip()}")

def verify(project:Path)->None:
    compile_result=run(["python3","-m","compileall","-q","."],cwd=project,timeout=300)
    if compile_result.returncode: raise RuntimeError(f"compile verification failed: {compile_result.stderr.strip()}")
    tests=run(["python3","-m","unittest","discover","-s","tests","-p","test_*.py","-v"],cwd=project,timeout=600)
    if tests.returncode: raise RuntimeError(f"test verification failed: {tests.stdout[-6000:]}\n{tests.stderr[-3000:]}")

def publish(project:Path,job_id:str,objective:str)->str:
    status=run(["git","status","--short"],cwd=project)
    if not status.stdout.strip(): raise RuntimeError("coding agent produced no repository changes")
    branch=f"aegis/{job_id}"
    commands=[
        ["git","checkout","-b",branch],
        ["git","add","-A"],
        ["git","-c","user.name=AEGIS Worker","-c","user.email=aegis-worker@users.noreply.github.com",
         "commit","-m",f"AEGIS: {objective[:60]}"],
    ]
    for cmd in commands:
        result=run(cmd,cwd=project,timeout=120)
        if result.returncode: raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    pushed=run(["git","push","-u","origin",branch],cwd=project,timeout=300)
    if pushed.returncode: raise RuntimeError(pushed.stderr.strip() or pushed.stdout.strip())
    pr=run(["gh","pr","create","--base","master","--head",branch,
            "--title",f"AEGIS: {objective[:80]}",
            "--body",f"Automated AEGIS implementation for job {job_id}.\n\nObjective: {objective}"],
           cwd=project,timeout=120)
    if pr.returncode: raise RuntimeError(pr.stderr.strip() or pr.stdout.strip())
    return pr.stdout.strip()

def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--project",required=True)
    parser.add_argument("--job-id",required=True)
    parser.add_argument("--capability",required=True)
    parser.add_argument("--issue",required=True)
    parser.add_argument("--objective",required=True)
    args=parser.parse_args()
    project=Path(args.project).resolve()
    if not (project/".git").exists(): raise RuntimeError("target project is not a git checkout")
    if not args.objective.strip() or len(args.objective)>MAX_OBJECTIVE:
        raise RuntimeError(f"objective must be 1-{MAX_OBJECTIVE} characters")
    if args.capability not in ALLOWED_CAPABILITIES:
        raise RuntimeError(f"unsupported remote worker capability: {args.capability}")
    ensure_clean(project)
    print(json.dumps({"stage":"inspect","job_id":args.job_id,"capability":args.capability}))
    context=snapshot(project)
    plan=model_plan(args.objective,context)
    print(json.dumps({"stage":"plan","summary":plan.get("summary","")}))
    apply_patch(project,str(plan.get("patch","")))
    verify(project)
    pr=publish(project,args.job_id,args.objective)
    print(json.dumps({"stage":"published","job_id":args.job_id,"pull_request":pr}))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
