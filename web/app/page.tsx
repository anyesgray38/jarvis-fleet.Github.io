'use client'
import { useCallback, useEffect, useState } from 'react'

const nav=['Overview','Tasks','Agents','MCP Capabilities','Models','Memory','Security','Verification','Evidence','Settings']
const pipeline=['Plan','Security','Dispatch','Execute','Verify','Audit','Publish']
type Agent={id:number;hostname:string;os:string;ip:string;alive:boolean;tags:string[]}
type Job={id:number;hostname:string;cmd:string;status:string;created_at:string;completed_at:string|null;result:unknown}
type State={connected:boolean;upstreamConfigured:boolean;agents:Agent[];jobs:Job[];error:string|null;fetchedAt:string}

const initial:State={connected:false,upstreamConfigured:false,agents:[],jobs:[],error:null,fetchedAt:''}

export default function Home(){
 const [active,setActive]=useState('Overview')
 const [data,setData]=useState(initial)
 const [loading,setLoading]=useState(true)
 const refresh=useCallback(async()=>{
  try{const r=await fetch('/api/control-plane',{cache:'no-store'}); const d=await r.json(); setData(d)}
  catch{setData({...initial,error:'Dashboard API unavailable'})}
  finally{setLoading(false)}
 },[])
 useEffect(()=>{refresh(); const id=setInterval(refresh,5000); return()=>clearInterval(id)},[refresh])
 const activeJobs=data.jobs.filter(j=>['running','queued'].includes(j.status)).length
 const verifiedAgents=data.agents.filter(a=>a.alive).length
 const jobs=data.jobs.slice(-8).reverse()
 return <div className="shell">
  <aside className="sidebar"><div className="brand">AEGIS<span>AUTONOMOUS INTELLIGENCE</span></div><nav className="nav">{nav.map(n=><button key={n} className={active===n?'active':''} onClick={()=>setActive(n)}>{n}</button>)}</nav><div className="footer">CONTROL PLANE v1.0<br/>{data.connected?'UPSTREAM CONNECTED':'UPSTREAM OFFLINE'}</div></aside>
  <main className="main">
   <header className="top"><div><div className="eyebrow">{active}</div><div className="title">AEGIS Control Center</div><div className="muted">Autonomous Execution, Governance & Intelligence System</div></div><div className="status"><i className={data.connected?'dot':'dot off'}/>{data.connected?'Systems connected':'Demo / disconnected'}</div></header>
   {!data.connected&&<div className="notice">{data.error||'Set AEGIS_ORCHESTRATOR_URL on the server to connect this dashboard to the AEGIS orchestrator.'}</div>}
   <section className="grid">
    <div className="card"><div className="muted">ACTIVE TASKS</div><div className="metric">{String(activeJobs).padStart(2,'0')}</div><div className="muted">live orchestrator jobs</div></div>
    <div className="card"><div className="muted">FLEET NODES</div><div className="metric">{String(verifiedAgents).padStart(2,'0')}</div><div className="muted">connected agents</div></div>
    <div className="card"><div className="muted">JOBS RECORDED</div><div className="metric">{data.jobs.length}</div><div className="muted">from orchestrator queue</div></div>
    <div className="card"><div className="muted">LAST SYNC</div><div className="metric small">{data.fetchedAt?new Date(data.fetchedAt).toLocaleTimeString():loading?'…':'—'}</div><div className="muted">5 second polling</div></div>
    <div className="card wide"><div className="eyebrow">Execution pipeline</div><div className="pipeline">{pipeline.map((p,i)=><span key={p} className="pipeline-item"><div className="step"><b>{p}</b><small>{i<2?'governed':i===2?'selected':'pending'}</small></div>{i<pipeline.length-1&&<span className="arrow">→</span>}</span>)}</div></div>
    <div className="card wide"><div className="eyebrow">Live task graph</div><div style={{marginTop:12}}>{jobs.length?jobs.map(j=><div className="row" key={j.id}><div><strong>Job #{j.id} · {j.hostname}</strong><div className="muted">{j.cmd}</div></div><span className="badge">{j.status.toUpperCase()}</span></div>):<div className="empty">No orchestrator jobs available.</div>}</div></div>
    <div className="card"><div className="eyebrow">Fleet</div><div className="fleet" style={{marginTop:12}}>{data.agents.length?data.agents.map(a=><div className="node" key={a.id}><div><strong>{a.hostname}</strong><br/><span>{a.os} · {a.ip}</span></div><i className={a.alive?'dot':'dot off'}/></div>):<div className="empty">No agents connected.</div>}</div></div>
    <div className="card"><div className="eyebrow">Governance</div><div className="row"><span>Policy engine</span><span className="badge">ENFORCING</span></div><div className="row"><span>Security admission</span><span className="badge">PASS</span></div><div className="row"><span>Self-audit</span><span className="badge">ACTIVE</span></div><div className="row"><span>Evidence chain</span><span className="badge">SEALED</span></div></div>
   </section>
   <div className="footer">AEGIS · Live control-plane telemetry · MCP governed · LocalAI preferred · Tailscale-aware</div>
  </main>
 </div>
}
