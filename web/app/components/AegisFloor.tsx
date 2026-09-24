'use client'

import { useMemo, useState } from 'react'

type Worker = { name: string; role: string; status: 'active' | 'queued' | 'idle' }
type Department = {
  id: string
  name: string
  manager: string
  managerRole: string
  color: string
  status: string
  throughput: string
  summary: string
  workers: Worker[]
}

const inboundDepartments: Department[] = [
  {
    id: 'web-intelligence',
    name: 'Web Intelligence',
    manager: 'Atlas',
    managerRole: 'Intake manager',
    color: '#79d8b0',
    status: 'LEARNING',
    throughput: '42 sources / hr',
    summary: 'Finds current, relevant signals across approved web sources.',
    workers: [
      { name: 'Scout-01', role: 'Web scout', status: 'active' },
      { name: 'Extract-02', role: 'Content extractor', status: 'active' },
      { name: 'Cite-03', role: 'Source verifier', status: 'queued' },
    ],
  },
  {
    id: 'wiki-reference',
    name: 'Wiki & Reference',
    manager: 'Scribe',
    managerRole: 'Reference manager',
    color: '#8fc6ff',
    status: 'SYNCHRONIZING',
    throughput: '18 references / hr',
    summary: 'Turns durable references into compact, cited knowledge packets.',
    workers: [
      { name: 'Wiki-01', role: 'Reference scout', status: 'active' },
      { name: 'Proof-02', role: 'Citation checker', status: 'active' },
      { name: 'Map-03', role: 'Topic mapper', status: 'idle' },
    ],
  },
  {
    id: 'memory-forge',
    name: 'Memory Forge',
    manager: 'Mnemia',
    managerRole: 'Knowledge manager',
    color: '#c8a5ff',
    status: 'DISTILLING',
    throughput: '286 packets ready',
    summary: 'Compresses source material so full context is retrieved only when needed.',
    workers: [
      { name: 'Chunk-01', role: 'Context chunker', status: 'active' },
      { name: 'Index-02', role: 'Memory indexer', status: 'active' },
      { name: 'Recall-03', role: 'Retrieval tester', status: 'queued' },
    ],
  },
]

const outboundDepartments: Department[] = [
  {
    id: 'shark-ops',
    name: 'Shark After Dark',
    manager: 'Harbor',
    managerRole: 'Business manager',
    color: '#f0bc88',
    status: 'OPERATING',
    throughput: 'Bookings + revenue',
    summary: 'Runs bookings, revenue visibility, security posture, and operator assistance.',
    workers: [
      { name: 'Booking-01', role: 'Booking coordinator', status: 'active' },
      { name: 'Revenue-02', role: 'Revenue analyst', status: 'active' },
      { name: 'Ops-03', role: 'Studio operator', status: 'queued' },
    ],
  },
  {
    id: 'code-factory',
    name: 'Aegis Codebase',
    manager: 'Forge',
    managerRole: 'Delivery manager',
    color: '#91c7ff',
    status: 'BUILDING',
    throughput: '3 changes in queue',
    summary: 'Plans, builds, tests, and ships governed product improvements.',
    workers: [
      { name: 'Build-01', role: 'Implementation agent', status: 'active' },
      { name: 'QA-02', role: 'Verification agent', status: 'active' },
      { name: 'Release-03', role: 'Release operator', status: 'idle' },
    ],
  },
  {
    id: 'customer-systems',
    name: 'Customer Systems',
    manager: 'Relay',
    managerRole: 'Service manager',
    color: '#e59bba',
    status: 'STANDING BY',
    throughput: '2 workflows ready',
    summary: 'Coordinates future messaging, customer care, and approved automations.',
    workers: [
      { name: 'Support-01', role: 'Service analyst', status: 'idle' },
      { name: 'Flow-02', role: 'Workflow designer', status: 'queued' },
      { name: 'Care-03', role: 'Response reviewer', status: 'idle' },
    ],
  },
]

const maintenanceDepartment: Department = {
  id: 'maintenance',
  name: 'Maintenance & Audit',
  manager: 'Sentinel',
  managerRole: 'Reliability manager',
  color: '#f09e8c',
  status: 'AUDITING',
  throughput: '4 recommendations',
  summary: 'Audits the system, finds drift, and routes upgrade recommendations to the responsible manager.',
  workers: [
    { name: 'Audit-01', role: 'Control auditor', status: 'active' },
    { name: 'Patch-02', role: 'Dependency watcher', status: 'active' },
    { name: 'Guide-03', role: 'Upgrade recommender', status: 'queued' },
    { name: 'Drill-04', role: 'Recovery tester', status: 'idle' },
  ],
}

const growth = [
  { label: 'Sources mapped', value: '1,248', change: '+84 this week', width: '78%' },
  { label: 'Distilled packets', value: '286', change: '+31 this week', width: '54%' },
  { label: 'Reusable skills', value: '74', change: '+8 this week', width: '38%' },
  { label: 'Agents promoted', value: '12', change: '+2 this month', width: '24%' },
]

export default function AegisFloor() {
  const [selectedId, setSelectedId] = useState('command')
  const [routed, setRouted] = useState<string[]>([])
  const departments = [...inboundDepartments, ...outboundDepartments, maintenanceDepartment]
  const selected = useMemo(() => departments.find(department => department.id === selectedId), [departments, selectedId])

  function routeRecommendation(id: string) {
    setRouted(current => current.includes(id) ? current : [...current, id])
  }

  return <section className="floor-page">
    <div className="floor-intro">
      <div>
        <div className="eyebrow">AEGIS OPERATIONS FLOOR · COMMAND VIEW</div>
        <h1>One brain. Every station. A system that grows.</h1>
        <p className="floor-lede">Aegis coordinates the chain of command: knowledge comes in, departments turn it into useful work, and approved outcomes move out into your businesses and codebases.</p>
      </div>
      <div className="floor-live-state"><i className="dot" /><div><strong>LEARNING LOOP ACTIVE</strong><span>Last cycle completed 2m ago</span></div></div>
    </div>

    <div className="floor-kpis">
      <FloorKpi label="Agents on floor" value="26" note="7 managers · 19 workers" />
      <FloorKpi label="Work in motion" value="18" note="6 inbound · 8 outbound · 4 audit" />
      <FloorKpi label="Knowledge ready" value="92%" note="distilled before retrieval" />
      <FloorKpi label="System growth" value="+12%" note="month-over-month capacity" />
    </div>

    <div className="floor-map">
      <section className="floor-lane inbound-lane">
        <LaneHeading direction="INBOUND" title="Knowledge receiving" detail="Web scraping · wiki search · source distillation" />
        <div className="lane-flow"><span /> <b>RECEIVE</b><span /> <b>VERIFY</b><span /> <b>COMPRESS</b></div>
        <div className="department-stack">{inboundDepartments.map(department => <DepartmentCard key={department.id} department={department} selected={selectedId === department.id} onSelect={setSelectedId} />)}</div>
        <div className="compact-note"><span className="note-icon">↓</span><div><strong>Memory policy</strong><p>Keep a compact packet in active memory. Retrieve the full source only when a manager requests it.</p></div></div>
      </section>

      <section className="command-bay">
        <div className="bay-label"><span>COMMAND BAY</span><i className="signal-line" /><span>ACCOUNTABILITY CENTER</span></div>
        <button type="button" className={selectedId === 'command' ? 'brain-card selected' : 'brain-card'} onClick={() => setSelectedId('command')}>
          <div className="brain-visual" aria-hidden="true"><div className="brain-orbit orbit-one" /><div className="brain-orbit orbit-two" /><div className="brain-orbit orbit-three" /><div className="brain-core"><span>AEGIS</span><small>central brain</small></div><div className="brain-pulse" /></div>
          <div className="brain-copy"><div className="eyebrow">CENTRAL COMMAND</div><h2>Aegis</h2><p>Owns the workflow, assigns responsibility, and keeps every manager accountable for the workers beneath them.</p></div>
          <div className="command-status"><span><i className="dot" /> Orchestrating</span><span>26 agents visible</span></div>
        </button>
        <div className="chain-of-command">
          <div className="chain-title">CHAIN OF COMMAND</div>
          <div className="chain-row"><span className="chain-node brain-node">Aegis</span><span className="chain-arrow">↓</span><span className="chain-node manager-node">Department managers</span><span className="chain-arrow">↓</span><span className="chain-node worker-node">Worker agents</span></div>
          <p>Workers report to managers. Managers report to Aegis. No agent is orphaned from ownership.</p>
        </div>
        <div className="command-queue">
          <div className="queue-head"><span>LIVE COMMAND QUEUE</span><span className="badge">GOVERNED</span></div>
          <QueueItem label="Scribe → Memory Forge" task="Distill the new reference packet" status="RUNNING" />
          <QueueItem label="Harbor → Shark After Dark" task="Reconcile booking pipeline" status="READY" />
          <QueueItem label="Sentinel → Forge" task="Review dependency upgrade" status="ROUTED" />
        </div>
      </section>

      <section className="floor-lane outbound-lane">
        <LaneHeading direction="OUTBOUND" title="Work dispatch" detail="Businesses · code · customer systems" />
        <div className="lane-flow"><span /> <b>PLAN</b><span /> <b>EXECUTE</b><span /> <b>VERIFY</b></div>
        <div className="department-stack">{outboundDepartments.map(department => <DepartmentCard key={department.id} department={department} selected={selectedId === department.id} onSelect={setSelectedId} />)}</div>
        <div className="compact-note"><span className="note-icon">↑</span><div><strong>Output boundary</strong><p>Every external action is routed through a manager, verified, and recorded before publication.</p></div></div>
      </section>
    </div>

    <section className="growth-panel">
      <div className="growth-copy"><div className="eyebrow">VISIBLE GROWTH LEDGER</div><h2>Watch the system become more capable.</h2><p>Inbound knowledge increases the floor's capacity without flooding active memory. Promotion happens when a worker demonstrates reliability.</p><div className="growth-legend"><span><i className="legend-dot knowledge-dot" /> knowledge</span><span><i className="legend-dot agent-dot" /> agent capacity</span></div></div>
      <div className="growth-metrics">{growth.map(item => <div className="growth-metric" key={item.label}><div className="growth-metric-top"><span>{item.label}</span><strong>{item.value}</strong></div><div className="growth-bar"><i style={{ width: item.width }} /></div><small>{item.change}</small></div>)}</div>
    </section>

    <section className="maintenance-bay">
      <div className="maintenance-head"><div><div className="eyebrow">MAINTENANCE DEPARTMENT · AUDIT BAY</div><h2>Keep the floor healthy.</h2><p className="muted large">Sentinel audits drift, security, dependencies, and recovery paths, then routes recommendations to the manager who owns the change.</p></div><div className="maintenance-badge"><i className="dot" /> 4 recommendations ready</div></div>
      <div className="maintenance-grid"><DepartmentCard department={maintenanceDepartment} selected={selectedId === maintenanceDepartment.id} onSelect={setSelectedId} /><div className="recommendation-list"><Recommendation title="Upgrade web runtime dependencies" owner="Forge · Aegis Codebase" priority="HIGH" id="runtime" routed={routed.includes('runtime')} onRoute={routeRecommendation} /><Recommendation title="Add source freshness checks" owner="Scribe · Wiki & Reference" priority="MEDIUM" id="freshness" routed={routed.includes('freshness')} onRoute={routeRecommendation} /><Recommendation title="Run disaster-recovery drill" owner="Sentinel · Maintenance" priority="MEDIUM" id="recovery" routed={routed.includes('recovery')} onRoute={routeRecommendation} /></div></div>
    </section>

    <div className="station-detail"><div><div className="eyebrow">SELECTED STATION</div><h3>{selected ? selected.name : 'Aegis central command'}</h3><p>{selected ? selected.summary : 'Select any station to inspect its manager, workers, and operating responsibility.'}</p></div><div className="station-detail-meta">{selected ? <><span><strong>{selected.manager}</strong> · {selected.managerRole}</span><span>{selected.workers.length} workers reporting</span><span className="station-detail-status"><i className="dot" /> {selected.status}</span></> : <span>Command owns the whole floor.</span>}</div></div>
  </section>
}

function FloorKpi({ label, value, note }: { label: string; value: string; note: string }) {
  return <div className="floor-kpi"><span>{label}</span><strong>{value}</strong><small>{note}</small></div>
}

function LaneHeading({ direction, title, detail }: { direction: string; title: string; detail: string }) {
  return <div className="lane-heading"><div className={direction === 'INBOUND' ? 'lane-icon inbound-icon' : 'lane-icon outbound-icon'}>{direction === 'INBOUND' ? '↓' : '↑'}</div><div><div className="eyebrow">{direction} LANE</div><h2>{title}</h2><p>{detail}</p></div></div>
}

function DepartmentCard({ department, selected, onSelect }: { department: Department; selected: boolean; onSelect: (id: string) => void }) {
  return <button type="button" className={selected ? 'department-card selected' : 'department-card'} style={{ borderLeftColor: department.color }} onClick={() => onSelect(department.id)}>
    <div className="department-top"><div><strong>{department.name}</strong><span>{department.status}</span></div><i className="department-pulse" style={{ background: department.color }} /></div>
    <div className="department-manager"><span className="manager-avatar" style={{ borderColor: department.color }}>{department.manager.slice(0, 1)}</span><div><b>{department.manager}</b><small>{department.managerRole}</small></div><em>{department.throughput}</em></div>
    <div className="worker-row">{department.workers.map(worker => <span key={worker.name} title={worker.role}><i className={worker.status === 'active' ? 'worker-dot active' : worker.status === 'queued' ? 'worker-dot queued' : 'worker-dot'} />{worker.name}</span>)}</div>
  </button>
}

function QueueItem({ label, task, status }: { label: string; task: string; status: string }) {
  return <div className="queue-item"><div><strong>{label}</strong><span>{task}</span></div><em>{status}</em></div>
}

function Recommendation({ title, owner, priority, id, routed, onRoute }: { title: string; owner: string; priority: string; id: string; routed: boolean; onRoute: (id: string) => void }) {
  return <div className="recommendation"><div className="recommendation-mark">{priority === 'HIGH' ? '!' : '↗'}</div><div className="recommendation-content"><strong>{title}</strong><span>{owner}</span></div><button type="button" onClick={() => onRoute(id)} disabled={routed}>{routed ? 'ROUTED' : 'SEND TO MANAGER'}</button></div>
}
