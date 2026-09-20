"""Full Linux CLI for the AEGIS/Jarvis control plane."""
from __future__ import annotations
import argparse, json, os, shlex, sys
from pathlib import Path
from typing import Any, Sequence

from jarvis.autonomy import AutonomyController, TaskEnvelope, TrustLevel, simulate
from jarvis.capabilities import CapabilityRegistry
from security.safety import SafetySettings

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CAPABILITIES = ROOT / "capabilities" / "registry.json"
DEFAULT_POLICY = ROOT / "security" / "policy.json"
DEFAULT_SAFETY = Path(os.getenv("JARVIS_SAFETY_CONFIG", ".jarvis/safety.json"))
BANNER = r"""
   █████╗ ███████╗ ██████╗ ██╗███████╗
  ██╔══██╗██╔════╝██╔════╝ ██║██╔════╝
  ███████║█████╗  ██║  ███╗██║███████╗
  ██╔══██║██╔══╝  ██║   ██║██║╚════██║
  ██║  ██║███████╗╚██████╔╝██║███████║
  ╚═╝  ╚═╝╚══════╝ ╚═════╝ ╚═╝╚══════╝
                 A E G I S
       AI EXECUTE • GOVERN • INSPECT • SECURE
"""

def _json(v: Any) -> str: return json.dumps(v, indent=2, sort_keys=True, default=str)
def _settings(args): return SafetySettings(args.safety_config)
def _trust(v: str) -> TrustLevel:
    try: return TrustLevel[v.upper()]
    except KeyError as exc: raise ValueError(f"unknown trust level: {v}") from exc

def build_parser() -> argparse.ArgumentParser:
    p=argparse.ArgumentParser(prog="jarvis", description="AEGIS control-plane CLI")
    p.add_argument("--version", action="version", version="AEGIS/Jarvis CLI 1.0")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument("--safety-config", default=str(DEFAULT_SAFETY))
    p.add_argument("--capabilities", default=str(DEFAULT_CAPABILITIES))
    sub=p.add_subparsers(dest="command")
    for name, help_text in {
        "status":"show AEGIS runtime status","capabilities":"list registered capabilities",
        "agents":"show configured agent/fleet status","providers":"show configured model providers",
        "logs":"show recent local evidence/activity","memory":"show local memory layer status",
        "doctor":"run local control-plane diagnostics","help":"show command help",
    }.items(): sub.add_parser(name, help=help_text)
    ask=sub.add_parser("ask",help="ask the governed model runtime"); ask.add_argument("query"); ask.add_argument("--purpose",default="general"); ask.add_argument("--external",action="store_true")
    ins=sub.add_parser("inspect",help="inspect a local file or directory"); ins.add_argument("target",nargs="?",default=".")
    plan=sub.add_parser("plan",help="create a task envelope without executing"); plan.add_argument("objective"); plan.add_argument("--capability",default="filesystem.read"); plan.add_argument("--trust",default="PREPARE"); plan.add_argument("--input",default="{}")
    run=sub.add_parser("run",help="execute one governed capability"); run.add_argument("objective"); run.add_argument("--capability",required=True); run.add_argument("--trust",default="PREPARE"); run.add_argument("--input",default="{}"); run.add_argument("--security-json"); run.add_argument("--execute",action="store_true")
    sim=sub.add_parser("simulate",help="dry-run a task"); sim.add_argument("objective"); sim.add_argument("--capability",required=True); sim.add_argument("--trust",default="PREPARE")
    safety=sub.add_parser("safety",help="manage runtime safety controls"); ss=safety.add_subparsers(dest="safety_command"); ss.add_parser("list"); en=ss.add_parser("enable"); en.add_argument("control"); dis=ss.add_parser("disable"); dis.add_argument("control"); sh=ss.add_parser("show"); sh.add_argument("control")
    tog=sub.add_parser("toggle",help="short form for a safety switch"); tog.add_argument("control"); tog.add_argument("state",choices=("on","off"))
    return p

def _emit(args,payload,text=None):
    print(_json(payload) if args.json else (payload if isinstance(payload,str) else (text if text is not None else _json(payload))))
    return 0

def _status(args):
    s=_settings(args)
    return {"system":"AEGIS","cli":"ready","safety":s.snapshot(),"safety_mode":"ENFORCING","trust_default":"PREPARE","evidence_store":str(ROOT/"evidence"),"model_runtime":f"http://127.0.0.1:{os.getenv('AEGIS_MODEL_PORT','8891')}"}

def _caps(args):
    path=Path(args.capabilities)
    if not path.exists(): raise FileNotFoundError(f"capability registry not found: {path}")
    return CapabilityRegistry(path).list()

def _input(raw): 
    value=json.loads(raw)
    if not isinstance(value,dict): raise ValueError("--input must be a JSON object")
    return value

def _envelope(args):
    return TaskEnvelope.create(args.objective,args.capability,_input(args.input),trust_required=_trust(args.trust))

def _inspect(target):
    path=Path(target).expanduser().resolve()
    if not path.exists(): raise FileNotFoundError(f"target not found: {path}")
    if path.is_file(): return {"path":str(path),"type":"file","bytes":path.stat().st_size}
    entries=sorted(path.iterdir(),key=lambda p:(not p.is_dir(),p.name.lower()))
    return {"path":str(path),"type":"directory","entries":[{"name":p.name,"type":"directory" if p.is_dir() else "file"} for p in entries[:200]],"truncated":len(entries)>200}

def _safety(args):
    s=_settings(args)
    if args.safety_command in {None,"list"}: return _emit(args,s.snapshot())
    if args.safety_command=="show":
        return _emit(args,{args.control:s.enabled(args.control)})
    enabled=args.safety_command=="enable"; s.set(args.control,enabled)
    return _emit(args,{args.control:enabled})

def _doctor(args):
    checks={"python":sys.version.split()[0],"repository_root":ROOT.exists(),"security_policy":DEFAULT_POLICY.exists(),"safety_controls":True,"capability_registry":Path(args.capabilities).exists(),"evidence_directory":(ROOT/"evidence").exists()}
    checks["healthy"]=all(v is True for k,v in checks.items() if k!="python"); return checks

def _chat(query,purpose,external):
    from jarvis.model_service import ModelRuntime
    return ModelRuntime().chat(messages=[{"role":"user","content":query}],purpose=purpose,local_only=not external,allow_external=external)

def _run(args):
    envelope=_envelope(args)
    task={"task_id":envelope.task_id,"objective":envelope.objective,"capability":envelope.capability,"trust_required":int(envelope.trust_required),"input":envelope.input}
    if not args.execute: return _emit(args,task,text=f"DRY RUN\nTask: {envelope.task_id}\nCapability: {envelope.capability}\nUse --execute to dispatch through AEGIS.")
    if not args.security_json: print("Execution blocked: --security-json is required for policy admission.",file=sys.stderr); return 2
    security=json.loads(Path(args.security_json).read_text(encoding="utf-8"))
    from jarvis.dispatcher import Dispatcher
    from security.policy import Policy
    from actions.fabric import default_fabric, ActionContext
    registry=CapabilityRegistry(args.capabilities); fabric=default_fabric(); workspace=Path.cwd().resolve()
    def executor(t,cap):
        action=str(cap.get("action",cap["id"]))
        return fabric.execute(action,t.get("input",{}),ActionContext(t["task_id"],workspace)).output
    result=Dispatcher(registry,Policy(DEFAULT_POLICY),executor,safety=_settings(args)).dispatch(task,security=security)
    return _emit(args,result.__dict__)

def execute(args):
    if args.command in {None,"help"}: print(BANNER); build_parser().print_help(); return 0
    if args.command=="status": return _emit(args,_status(args))
    if args.command=="safety": return _safety(args)
    if args.command=="toggle":
        args.safety_command="enable" if args.state=="on" else "disable"; return _safety(args)
    if args.command=="capabilities": return _emit(args,_caps(args))
    if args.command=="inspect": return _emit(args,_inspect(args.target))
    if args.command=="doctor": return _emit(args,_doctor(args))
    if args.command=="ask":
        result=_chat(args.query,args.purpose,args.external); return _emit(args,result,text=result["response"]["content"])
    if args.command=="plan":
        e=_envelope(args); return _emit(args,{"task_id":e.task_id,"objective":e.objective,"capability":e.capability,"trust_required":e.trust_required.name,"input":e.input})
    if args.command=="simulate":
        e=TaskEnvelope.create(args.objective,args.capability,trust_required=_trust(args.trust)); return _emit(args,simulate(e,AutonomyController()).__dict__)
    if args.command=="run": return _run(args)
    if args.command in {"agents","providers","logs","memory"}: return _emit(args,{"command":args.command,"status":"local inspection endpoint not configured","governance":"no direct execution bypass"})
    return 2

def interactive(base):
    print(BANNER); print("Type 'help' for commands. Type 'exit' or Ctrl-D to leave.")
    while True:
        try: line=input("AEGIS> ").strip()
        except EOFError: print(); return 0
        if not line: continue
        if line in {"exit","quit"}: return 0
        try:
            parsed=build_parser().parse_args(["--safety-config",base.safety_config,*shlex.split(line)])
            execute(parsed)
        except SystemExit: continue
        except Exception as exc: print(f"ERROR: {exc}",file=sys.stderr)

def main(argv: Sequence[str]|None=None):
    args_list=list(argv) if argv is not None else sys.argv[1:]
    if not args_list: return interactive(build_parser().parse_args([]))
    try: return execute(build_parser().parse_args(args_list))
    except (ValueError,FileNotFoundError,json.JSONDecodeError) as exc: print(f"ERROR: {exc}",file=sys.stderr); return 2

if __name__=="__main__": raise SystemExit(main())
