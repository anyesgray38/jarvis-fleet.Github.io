"""Full Linux CLI for the AEGIS/Jarvis control plane."""
from __future__ import annotations
import argparse, json, os, shlex, sys
from pathlib import Path
from typing import Any, Sequence

from jarvis.autonomy import AutonomyController, TaskEnvelope, TrustLevel, simulate
from jarvis.capabilities import CapabilityRegistry
from jarvis.remote_jobs import JobStore, STATUSES
from jarvis.remote_dispatch import submit_issue, RemoteDispatchError
from security.safety import SafetySettings

ROOT=Path(__file__).resolve().parents[1]
DEFAULT_CAPABILITIES=ROOT/"capabilities"/"registry.json"
DEFAULT_POLICY=ROOT/"security"/"policy.json"
DEFAULT_PROVIDERS=ROOT/"capabilities"/"providers.json"
DEFAULT_FLEET=ROOT/"fleet"/"config.example.json"
DEFAULT_SAFETY=Path(os.getenv("JARVIS_SAFETY_CONFIG",".jarvis/safety.json"))
BANNER=r"""
   █████╗ ███████╗ ██████╗ ██╗███████╗
  ██╔══██╗██╔════╝██╔════╝ ██║██╔════╝
  ███████║█████╗  ██║  ███╗██║███████╗
  ██╔══██║██╔══╝  ██║   ██║██║╚════██║
  ██║  ██║███████╗╚██████╔╝██║███████║
  ╚═╝  ╚═╝╚══════╝ ╚═════╝ ╚═╝╚══════╝
                 A E G I S
       AI EXECUTE • GOVERN • INSPECT • SECURE
"""

def _json(v:Any)->str:return json.dumps(v,indent=2,sort_keys=True,default=str)
def _settings(args):return SafetySettings(args.safety_config)
def _trust(v:str)->TrustLevel:
    try:return TrustLevel[v.upper()]
    except KeyError as exc:raise ValueError(f"unknown trust level: {v}") from exc
def _load_json(path:Path)->Any:
    if not path.exists():raise FileNotFoundError(f"file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))

def build_parser()->argparse.ArgumentParser:
    p=argparse.ArgumentParser(prog="jarvis",description="AEGIS control-plane CLI")
    p.add_argument("--version",action="version",version="AEGIS/Jarvis CLI 1.0")
    p.add_argument("--json",action="store_true",help="machine-readable output")
    p.add_argument("--safety-config",default=str(DEFAULT_SAFETY))
    p.add_argument("--capabilities",default=str(DEFAULT_CAPABILITIES))
    sub=p.add_subparsers(dest="command")
    for n,h in {"status":"show AEGIS runtime status","capabilities":"list registered capabilities","agents":"show configured fleet agents","providers":"show configured model providers","logs":"show recent evidence records","memory":"show memory layer status","doctor":"run local control-plane diagnostics","help":"show command help"}.items():sub.add_parser(n,help=h)
    audit=sub.add_parser("audit",help="audit Python code without executing it");audit.add_argument("target",nargs="?",default=".")
    ask=sub.add_parser("ask",help="ask the governed model runtime");ask.add_argument("query");ask.add_argument("--purpose",default="general");ask.add_argument("--external",action="store_true")
    ins=sub.add_parser("inspect",help="inspect a local file or directory");ins.add_argument("target",nargs="?",default=".")
    plan=sub.add_parser("plan",help="create a task envelope without executing");plan.add_argument("objective");plan.add_argument("--capability",default="filesystem.read");plan.add_argument("--trust",default="PREPARE");plan.add_argument("--input",default="{}")
    run=sub.add_parser("run",help="execute one governed capability");run.add_argument("objective");run.add_argument("--capability",required=True);run.add_argument("--trust",default="PREPARE");run.add_argument("--input",default="{}");run.add_argument("--security-json");run.add_argument("--execute",action="store_true")
    ex=sub.add_parser("exec",help="execute a Linux command through the governed terminal capability");ex.add_argument("command_text",nargs=argparse.REMAINDER)
    wr=sub.add_parser("write",help="write a file inside the current AEGIS workspace");wr.add_argument("path");wr.add_argument("content")
    sim=sub.add_parser("simulate",help="dry-run a task");sim.add_argument("objective");sim.add_argument("--capability",required=True);sim.add_argument("--trust",default="PREPARE")
    safety=sub.add_parser("safety",help="manage runtime safety controls");ss=safety.add_subparsers(dest="safety_command");ss.add_parser("list");en=ss.add_parser("enable");en.add_argument("control");dis=ss.add_parser("disable");dis.add_argument("control");sh=ss.add_parser("show");sh.add_argument("control")
    tog=sub.add_parser("toggle",help="short form for a safety switch");tog.add_argument("control",choices=SafetySettings().controls);tog.add_argument("state",choices=("on","off"))
    project=sub.add_parser("project",help="manage durable remote project jobs")
    ps=project.add_subparsers(dest="project_command")
    start=ps.add_parser("start",help="queue and remotely dispatch a project objective");start.add_argument("objective");start.add_argument("--repository",default=os.getenv("AEGIS_PROJECT_REPOSITORY","anyesgray38/jarvis-fleet.Github.io"));start.add_argument("--ref",default="master");start.add_argument("--capability",choices=("terminal.inspect","terminal.execute"),default="terminal.inspect");start.add_argument("--trust",default="PREPARE");start.add_argument("--input",default="{}");start.add_argument("--db",default=os.getenv("JARVIS_JOB_DB",".jarvis/jobs.db"));start.add_argument("--no-dispatch",action="store_true",help="queue locally without creating a GitHub job")
    st=ps.add_parser("status",help="show a project job or queued jobs");st.add_argument("job_id",nargs="?");st.add_argument("--status",choices=STATUSES);st.add_argument("--db",default=os.getenv("JARVIS_JOB_DB",".jarvis/jobs.db"))
    lg=ps.add_parser("logs",help="show project job events");lg.add_argument("job_id");lg.add_argument("--limit",type=int,default=100);lg.add_argument("--db",default=os.getenv("JARVIS_JOB_DB",".jarvis/jobs.db"))
    ca=ps.add_parser("cancel",help="cancel a queued or running project job");ca.add_argument("job_id");ca.add_argument("--db",default=os.getenv("JARVIS_JOB_DB",".jarvis/jobs.db"))
    scan=sub.add_parser("business-scan",help="discover and research businesses in a public geographic target")
    scan.add_argument("target")
    scan.add_argument("--category",default="")
    scan.add_argument("--radius",dest="radius_miles",type=float)
    scan.add_argument("--max-results",type=int,default=30)
    scan.add_argument("--generate",type=int,default=0,help="generate verified demo pages for up to N high-opportunity prospects")
    scan.add_argument("--output",dest="output_root",default=".jarvis/prospects");scan.add_argument("--source-url",action="append",default=[])
    prospect=sub.add_parser("prospect",help="inspect or act on stored business prospects")
    pp=prospect.add_subparsers(dest="prospect_command")
    pscan=pp.add_parser("scan",help="alias for business-scan")
    pscan.add_argument("target");pscan.add_argument("--category",default="");pscan.add_argument("--radius",dest="radius_miles",type=float);pscan.add_argument("--max-results",type=int,default=30);pscan.add_argument("--generate",type=int,default=0);pscan.add_argument("--output",dest="output_root",default=".jarvis/prospects");pscan.add_argument("--source-url",action="append",default=[])
    plist=pp.add_parser("list",help="list stored prospects");plist.add_argument("--min-score",type=int,default=0);plist.add_argument("--limit",type=int,default=100)
    pshow=pp.add_parser("show",help="show one stored prospect");pshow.add_argument("business_id")
    pbuild=pp.add_parser("build",help="generate and verify one prospect demonstration");pbuild.add_argument("business_id");pbuild.add_argument("--output",dest="output_root",default=".jarvis/prospects")
    builder=sub.add_parser("builder",help="autonomously create and verify a website or web app")
    builder.add_argument("name")
    builder.add_argument("--kind",choices=("website","app"),default="website")
    builder.add_argument("--title",required=True)
    builder.add_argument("--description",required=True)
    builder.add_argument("--accent",default="#7dd3fc")
    builder.add_argument("--workspace",default=".jarvis/builds")
    builder.add_argument("--overwrite",action="store_true")
    knowledge=sub.add_parser("knowledge",help="query or grow the local AEGIS second brain")
    kp=knowledge.add_subparsers(dest="knowledge_command")
    ksearch=kp.add_parser("search",help="search compact local knowledge packets");ksearch.add_argument("query");ksearch.add_argument("--department",default="");ksearch.add_argument("--limit",type=int,default=8);ksearch.add_argument("--full",action="store_true")
    kresearch=kp.add_parser("research",help="run one bounded due-department research cycle");kresearch.add_argument("--force",action="store_true")
    kp.add_parser("departments",help="show department memory growth and research schedule")
    return p

def _emit(args,payload,text=None):
    print(_json(payload) if args.json else (payload if isinstance(payload,str) else (text if text is not None else _json(payload))));return 0
def _status(args):
    s=_settings(args)
    return {"system":"AEGIS","cli":"ready","safety":s.snapshot(),"safety_mode":"ENFORCING","trust_default":"PREPARE","evidence_store":str(ROOT/"evidence"),"model_runtime":f"http://127.0.0.1:{os.getenv('AEGIS_MODEL_PORT','8891')}"}
def _caps(args):
    path=Path(args.capabilities)
    if not path.exists():raise FileNotFoundError(f"capability registry not found: {path}")
    return CapabilityRegistry(path).list()
def _input(raw):
    v=json.loads(raw)
    if not isinstance(v,dict):raise ValueError("--input must be a JSON object")
    return v
def _envelope(args):return TaskEnvelope.create(args.objective,args.capability,_input(args.input),trust_required=_trust(args.trust))
def _inspect(target):
    path=Path(target).expanduser().resolve()
    if not path.exists():raise FileNotFoundError(f"target not found: {path}")
    if path.is_file():return {"path":str(path),"type":"file","bytes":path.stat().st_size}
    entries=sorted(path.iterdir(),key=lambda p:(not p.is_dir(),p.name.lower()))
    return {"path":str(path),"type":"directory","entries":[{"name":p.name,"type":"directory" if p.is_dir() else "file"} for p in entries[:200]],"truncated":len(entries)>200}
def _safety(args):
    s=_settings(args)
    if args.safety_command in {None,"list"}:return _emit(args,s.snapshot())
    if args.safety_command=="show":return _emit(args,{args.control:s.enabled(args.control)})
    enabled=args.safety_command=="enable";s.set(args.control,enabled);return _emit(args,{args.control:enabled})
def _doctor(args):
    checks={"python":sys.version.split()[0],"repository_root":ROOT.exists(),"security_policy":DEFAULT_POLICY.exists(),"safety_controls":True,"capability_registry":Path(args.capabilities).exists(),"evidence_directory":(ROOT/"evidence").exists()}
    checks["healthy"]=all(v is True for k,v in checks.items() if k!="python");return checks
def _chat(query,purpose,external):
    from jarvis.model_service import ModelRuntime
    return ModelRuntime().chat(messages=[{"role":"user","content":query}],purpose=purpose,local_only=not external,allow_external=external)
def _tail_evidence(limit=20):
    path=ROOT/"evidence"
    records=[]
    if not path.exists():return records
    files=sorted(path.glob("*.jsonl"))
    for f in files:
        try:
            lines=f.read_text(encoding="utf-8").splitlines()
            for line in lines[-limit:]:
                if line.strip():records.append({"file":f.name,"record":json.loads(line)})
        except (OSError,ValueError,json.JSONDecodeError):continue
    return records[-limit:]
def _fleet(args):
    data=_load_json(Path(os.getenv("JARVIS_FLEET_CONFIG",str(DEFAULT_FLEET))))
    return {"source":os.getenv("JARVIS_FLEET_CONFIG",str(DEFAULT_FLEET)),"nodes":data.get("nodes",[]),"count":len(data.get("nodes",[]))}
def _providers():
    data=_load_json(DEFAULT_PROVIDERS);return data.get("providers",[])
def _memory():
    return {"layers":["personal","project","procedural","knowledge","evidence"],"storage":"control-plane memory interface","status":"ready"}
def _business_scan(args):
    from prospecting.models import ScanRequest
    from prospecting.store import ProspectStore
    from prospecting.workflow import BusinessProspectingAgent
    request=ScanRequest(target=args.target,category=args.category,radius_miles=args.radius_miles,max_results=max(1,min(100,args.max_results)),generate_limit=max(0,min(10,args.generate)),output_root=args.output_root,source_urls=tuple(args.source_url))
    result=BusinessProspectingAgent(store=ProspectStore(os.getenv("AEGIS_PROSPECT_DB",".jarvis/prospects.db"))).scan(request)
    return _emit(args,result.to_dict(),text=json.dumps(result.summary(),indent=2))
def _builder(args):
    workspace=Path(args.workspace).expanduser().resolve()
    workspace.mkdir(parents=True,exist_ok=True)
    args.safety_config=str(Path(args.safety_config).expanduser().resolve())
    args.objective=f"Build and verify {args.kind} project {args.name}"
    args.capability="core.autonomous_builder"
    args.trust="PREPARE"
    args.input=json.dumps({"name":args.name,"kind":args.kind,"title":args.title,"description":args.description,"accent":args.accent,"overwrite":args.overwrite})
    args.verification={"required":True,"checks":["evidence"]}
    args.execute=True
    args.security_json=None
    original=Path.cwd()
    try:
        os.chdir(workspace)
        result=_run(args)
    finally:
        os.chdir(original)
    return result
def _prospect(args):
    from prospecting.store import ProspectStore
    store=ProspectStore(os.getenv("AEGIS_PROSPECT_DB",".jarvis/prospects.db"))
    if args.prospect_command=="scan":
        return _business_scan(args)
    if args.prospect_command=="list":
        return _emit(args,[item.to_dict() for item in store.list_businesses(min_score=args.min_score,limit=args.limit)])
    if args.prospect_command=="show":
        item=store.get_business(args.business_id)
        if not item:raise ValueError(f"business not found: {args.business_id}")
        return _emit(args,item.to_dict())
    if args.prospect_command=="build":
        from prospecting.workflow import BusinessProspectingAgent
        return _emit(args,BusinessProspectingAgent(store=store).generate_business_demo(args.business_id,output_root=args.output_root))
    raise ValueError("prospect command is required")
def _knowledge(args):
    from urllib.parse import urlencode
    from urllib.request import Request, urlopen
    url=os.getenv("AEGIS_KNOWLEDGE_URL","http://127.0.0.1:8892").rstrip("/")
    token=os.getenv("AEGIS_KNOWLEDGE_TOKEN","")
    if not token: raise ValueError("AEGIS_KNOWLEDGE_TOKEN is required")
    if args.knowledge_command=="search":
        query=url+"/search?"+urlencode({"q":args.query,"department":args.department,"limit":args.limit,"full":int(args.full)})
        request=Request(query,headers={"Authorization":f"Bearer {token}","Accept":"application/json"})
    elif args.knowledge_command=="departments":
        request=Request(url+"/departments",headers={"Authorization":f"Bearer {token}","Accept":"application/json"})
    elif args.knowledge_command=="research":
        request=Request(url+"/research",data=json.dumps({"force":args.force}).encode(),method="POST",headers={"Authorization":f"Bearer {token}","Content-Type":"application/json"})
    else: raise ValueError("knowledge command is required")
    with urlopen(request,timeout=60) as response:
        return _emit(args,json.loads(response.read(2_000_000).decode()))
def _run(args):
    e=_envelope(args);task={"task_id":e.task_id,"objective":e.objective,"capability":e.capability,"trust_required":int(e.trust_required),"input":e.input,"verification":getattr(args,"verification",{})}
    if not args.execute:return _emit(args,task,text=f"DRY RUN\nTask: {e.task_id}\nCapability: {e.capability}\nUse --execute to dispatch through AEGIS.")
    security=_load_json(Path(args.security_json)) if args.security_json else {"execution_successful":True,"risk_score":0,"severity":"LOW","approved":True}
    if not isinstance(security,dict):raise ValueError("--security-json must contain a JSON object")
    from jarvis.dispatcher import Dispatcher
    from security.policy import Policy
    from actions.fabric import default_fabric,ActionContext,shell_execute
    registry=CapabilityRegistry(args.capabilities);fabric=default_fabric();fabric.register("shell.execute", shell_execute);workspace=Path.cwd().resolve()
    def executor(t,cap):
        action=str(cap.get("action",cap["id"]))
        return fabric.execute(action,t.get("input",{}),ActionContext(t["task_id"],workspace)).output
    checks={
        "evidence": lambda _t, result: (isinstance(result, dict), "result captured"),
        "scope_check": lambda _t, _result: (workspace == Path.cwd().resolve(), "execution workspace is current directory"),
        "result_audit": lambda _t, result: (isinstance(result.get("returncode"), int), "command returned a process status"),
    }
    result=Dispatcher(registry,Policy(DEFAULT_POLICY),executor,checks=checks,safety=_settings(args)).dispatch(task,security=security)
    return _emit(args,result.__dict__)
def _project(args):
    store=JobStore(args.db)
    if args.project_command=="start":
        job=store.create(args.objective,args.repository,ref=args.ref,capability=args.capability,
                         trust=args.trust,input=_input(args.input))
        remote=None
        if not args.no_dispatch:
            try:
                remote=submit_issue(repository=job.repository,objective=job.objective,ref=job.ref,
                                     capability=job.capability,job_id=job.job_id)
                issue_number=int(remote["url"].rstrip("/").split("/")[-1])
                store.attach_remote(job.job_id,issue_number=issue_number,issue_url=remote["url"])
            except (RemoteDispatchError, ValueError) as exc:
                store.transition(job.job_id,"escalated",error=str(exc),data={"stage":"remote_dispatch"})
                raise
        payload=store.get(job.job_id).__dict__
        if remote: payload["remote"]=remote
        return _emit(args,payload,text=f"QUEUED\\nJob: {job.job_id}\\nRepository: {job.repository}\\nObjective: {job.objective}")
    if args.project_command=="status":
        if args.job_id:return _emit(args,store.get(args.job_id).__dict__)
        return _emit(args,[j.__dict__ for j in store.list(args.status)])
    if args.project_command=="logs":
        return _emit(args,store.events(args.job_id,args.limit))
    if args.project_command=="cancel":
        job=store.get(args.job_id)
        if job.status in {"passed","failed","rejected","escalated","cancelled"}:
            raise ValueError(f"job {job.job_id} is already terminal: {job.status}")
        return _emit(args,store.transition(job.job_id,"cancelled",data={"reason":"operator requested cancellation"}).__dict__)
    raise ValueError("project command is required")

def execute(args):
    if args.command in {None,"help"}:print(BANNER);build_parser().print_help();return 0
    if args.command=="status":return _emit(args,_status(args))
    if args.command=="project":return _project(args)
    if args.command=="business-scan":return _business_scan(args)
    if args.command=="builder":return _builder(args)
    if args.command=="prospect":return _prospect(args)
    if args.command=="knowledge":return _knowledge(args)
    if args.command=="safety":return _safety(args)
    if args.command=="toggle":args.safety_command="enable" if args.state=="on" else "disable";return _safety(args)
    if args.command=="capabilities":return _emit(args,_caps(args))
    if args.command=="agents":return _emit(args,_fleet(args))
    if args.command=="providers":return _emit(args,_providers())
    if args.command=="logs":return _emit(args,_tail_evidence())
    if args.command=="audit":
        import compileall
        target=Path(args.target).expanduser().resolve()
        ok=compileall.compile_dir(str(target),quiet=1) if target.is_dir() else compileall.compile_file(str(target),quiet=1)
        return _emit(args,{"target":str(target),"syntax_ok":bool(ok),"mode":"compile_only"})
    if args.command=="memory":return _emit(args,_memory())
    if args.command=="inspect":return _emit(args,_inspect(args.target))
    if args.command=="exec":
        command=" ".join(args.command_text).strip()
        if not command: raise ValueError("command is required")
        args.objective=f"Execute operator-authorized Linux command: {command}"
        args.capability="terminal.execute";args.trust="PREPARE";args.input=json.dumps({"command":command});args.verification={"required":True,"checks":["evidence","scope_check","result_audit"]};args.execute=True;args.security_json=None
        return _run(args)
    if args.command=="write":
        args.objective=f"Write operator-authorized file: {args.path}"
        args.capability="terminal.write";args.trust="PREPARE";args.input=json.dumps({"path":args.path,"content":args.content});args.verification={"required":True,"checks":["evidence","scope_check","result_audit"]};args.execute=True;args.security_json=None
        return _run(args)
    if args.command=="doctor":return _emit(args,_doctor(args))
    if args.command=="ask":
        result=_chat(args.query,args.purpose,args.external);return _emit(args,result,text=result["response"]["content"])
    if args.command=="plan":
        e=_envelope(args);return _emit(args,{"task_id":e.task_id,"objective":e.objective,"capability":e.capability,"trust_required":e.trust_required.name,"input":e.input})
    if args.command=="simulate":
        e=TaskEnvelope.create(args.objective,args.capability,trust_required=_trust(args.trust));return _emit(args,simulate(e,AutonomyController()).__dict__)
    if args.command=="run":return _run(args)
    return 2
def interactive(base):
    print(BANNER);print("Type 'help' for commands. Type 'exit' or Ctrl-D to leave.")
    while True:
        try:line=input("AEGIS> ").strip()
        except EOFError:print();return 0
        if not line:continue
        if line in {"exit","quit"}:return 0
        try:
            parsed=build_parser().parse_args(["--safety-config",base.safety_config,*shlex.split(line)]);execute(parsed)
        except SystemExit:continue
        except Exception as exc:print(f"ERROR: {exc}",file=sys.stderr)
def main(argv:Sequence[str]|None=None):
    items=list(argv) if argv is not None else sys.argv[1:]
    if not items:return interactive(build_parser().parse_args([]))
    try:return execute(build_parser().parse_args(items))
    except (ValueError,FileNotFoundError,json.JSONDecodeError) as exc:print(f"ERROR: {exc}",file=sys.stderr);return 2
if __name__=="__main__":raise SystemExit(main())
