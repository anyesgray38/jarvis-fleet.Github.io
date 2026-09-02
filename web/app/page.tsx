'use client'
import { useState } from 'react'

const nav=['Overview','Tasks','Agents','MCP Capabilities','Models','Memory','Security','Verification','Evidence','Settings']
const pipeline=['Plan','Security','Dispatch','Execute','Verify','Audit','Publish']
const tasks=[['Research market conditions','research.web_search','RUNNING'],['Route optimization','logistics.route_plan','READY'],['Local model evaluation','core.model_inference','PASSED'],['MCP capability audit','core.mcp_discovery','AUDIT']]

export default function Home(){
 const [active,setActive]=useState('Overview')
 return <div className="shell">
  <aside className="sidebar"><div className="brand">AEGIS<span>AUTONOMOUS INTELLIGENCE</span></div><nav className="nav">{nav.map(n=><button key={n} className={active===n?'active':''} onClick={()=>setActive(n)}>{n}</button>)}</nav><div className="footer">CONTROL PLANE v1.0<br/>FLEET ONLINE</div></aside>
  <main className="main">
   <header className="top"><div><div className="eyebrow">{active}</div><div className="title">AEGIS Control Center</div><div className="muted">Autonomous Execution, Governance & Intelligence System</div></div><div className="status"><i className="dot"/> Systems nominal</div></header>
   <section className="grid">
    <div className="card"><div className="muted">ACTIVE TASKS</div><div className="metric">07</div><div className="muted">+3 since last hour</div></div>
    <div className="card"><div className="muted">FLEET NODES</div><div className="metric">03</div><div className="muted">2 verified · 1 standby</div></div>
    <div className="card"><div className="muted">MCP TOOLS</div><div className="metric">142</div><div className="muted">118 admitted · 24 pending</div></div>
    <div className="card"><div className="muted">VERIFICATION</div><div className="metric">99.2%</div><div className="muted">last 100 executions</div></div>
    <div className="card wide"><div className="eyebrow">Execution pipeline</div><div className="pipeline">{pipeline.map((p,i)=><span key={p} style={{display:'flex',alignItems:'center',gap:7}}><div className="step"><b>{p}</b><small>{i<3?'complete':i===3?'active':'queued'}</small></div>{i<pipeline.length-1&&<span className="arrow">→</span>}</span>)}</div></div>
    <div className="card wide"><div className="eyebrow">Live task graph</div><div style={{marginTop:12}}>{tasks.map(t=><div className="row" key={t[0]}><div><strong>{t[0]}</strong><div className="muted">{t[1]}</div></div><span className="badge">{t[2]}</span></div>)}</div></div>
    <div className="card"><div className="eyebrow">Fleet</div><div className="fleet" style={{marginTop:12}}>{[['linux-worker','Tailscale · verified'],['iphone-node','Tailscale · connected'],['gpu-worker','Tailscale · standby']].map(n=><div className="node" key={n[0]}><div><strong>{n[0]}</strong><br/><span>{n[1]}</span></div><i className="dot"/></div>)}</div></div>
    <div className="card"><div className="eyebrow">Governance</div><div className="row"><span>Policy engine</span><span className="badge">ENFORCING</span></div><div className="row"><span>Security admission</span><span className="badge">PASS</span></div><div className="row"><span>Self-audit</span><span className="badge">ACTIVE</span></div><div className="row"><span>Evidence chain</span><span className="badge">SEALED</span></div></div>
   </section>
   <div className="footer">AEGIS · Private execution fabric · MCP governed · LocalAI preferred · Tailscale-aware</div>
  </main>
 </div>
}