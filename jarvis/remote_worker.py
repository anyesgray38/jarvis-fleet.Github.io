"""Remote AEGIS project worker: inspect, propose, safely apply, verify, and publish a PR."""
from __future__ import annotations
import argparse, json, subprocess
from pathlib import Path
from typing import Any

MAX_FILE_BYTES=40_000
MAX_CONTEXT=180_000

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
    return json.loads(result["response"]["content"])

def apply_patch(project:Path,patch:str)->None:
    if not patch.strip(): raise RuntimeError("coding agent returned no patch")
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
