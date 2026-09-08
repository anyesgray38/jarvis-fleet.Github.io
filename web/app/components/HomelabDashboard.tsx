'use client'

import { useCallback, useEffect, useState } from 'react'
import AegisChat from './AegisChat'

type Service = { status: string; error?: string | null; live?: number; total?: number; active?: number; data?: Record<string, unknown> | null }
type Telemetry = { overall: string; services: { control_center: Service; orchestrator: Service; model_runtime: Service; fleet: Service; jobs: Service }; timestamp: string }

const initial: Telemetry = {
  overall: 'offline',
  services: {
    control_center: { status: 'online' },
    orchestrator: { status: 'offline' },
    model_runtime: { status: 'offline' },
    fleet: { status: 'offline', live: 0, total: 0 },
    jobs: { status: 'offline', active: 0, total: 0 },
  },
  timestamp: '',
}

function stateLabel(status: string) {
  return status.toUpperCase()
}

export default function HomelabDashboard() {
  const [telemetry, setTelemetry] = useState<Telemetry>(initial)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    try {
      const response = await fetch('/api/homelab', { cache: 'no-store' })
      const data = await response.json()
      setTelemetry(data)
    } catch {
      setTelemetry(initial)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
    const id = setInterval(refresh, 5000)
    return () => clearInterval(id)
  }, [refresh])

  const { services } = telemetry

  return <section className="homelab-layout">
    <div className="card wide homelab-hero">
      <div>
        <div className="eyebrow">AEGIS HOMELAB</div>
        <h2>Control your infrastructure through AEGIS</h2>
        <p className="muted large">Chat with AEGIS, inspect the fleet, route local models, and eventually operate your entire homelab from one governed control plane.</p>
      </div>
      <div className={`health-state ${telemetry.overall}`}><i className={telemetry.overall === 'healthy' ? 'dot' : 'dot off'} />{telemetry.overall.toUpperCase()}</div>
    </div>

    <div className="homelab-services">
      <ServiceCard title="Control Center" service={services.control_center} />
      <ServiceCard title="Orchestrator" service={services.orchestrator} />
      <ServiceCard title="Model Runtime" service={services.model_runtime} />
      <ServiceCard title="Fleet" service={services.fleet} detail={`${services.fleet.live ?? 0}/${services.fleet.total ?? 0} nodes online`} />
      <ServiceCard title="Jobs" service={services.jobs} detail={`${services.jobs.active ?? 0} active · ${services.jobs.total ?? 0} recorded`} />
    </div>

    <div className="card wide">
      <div className="eyebrow">CONVERSATIONAL CONTROL</div>
      <p className="muted">The chat below is the beginning of the AEGIS operator interface. As the homelab fabric grows, requests will resolve into governed plans, capabilities, agents, execution, verification, and evidence.</p>
    </div>

    <div className="wide"><AegisChat /></div>

    <div className="card wide">
      <div className="eyebrow">HOMELAB ROADMAP</div>
      <div className="roadmap">
        {['Live telemetry', 'Persistent memory', 'Natural-language planning', 'Governed execution', 'Proxmox integration', 'Distributed model nodes', 'NAS / evidence storage', 'Autonomous operations'].map((item, index) => <div className="roadmap-item" key={item}><span>{String(index + 1).padStart(2, '0')}</span><strong>{item}</strong><small>{index === 0 ? 'ACTIVE' : 'PLANNED'}</small></div>)}
      </div>
      {loading && <div className="muted">Collecting homelab telemetry…</div>}
      {telemetry.timestamp && <div className="muted" style={{ marginTop: 12 }}>Last telemetry: {new Date(telemetry.timestamp).toLocaleTimeString()}</div>}
    </div>
  </section>
}

function ServiceCard({ title, service, detail }: { title: string; service: Service; detail?: string }) {
  return <div className="card service-card"><div className="eyebrow">{title}</div><div className="service-status"><i className={service.status === 'online' ? 'dot' : 'dot off'} /><strong>{stateLabel(service.status)}</strong></div><div className="muted">{detail || service.error || 'AEGIS service'}</div></div>
}
