'use client'

import { FormEvent, useState } from 'react'

type Message = { role: 'user' | 'assistant'; content: string }
type Reply = { ok: boolean; request_id?: string; route?: { provider: string; model: string; reason: string; score: number; constraints: Record<string, unknown> }; timing_ms?: number; response?: { content: string }; error?: string }

const purposes = ['general', 'planning', 'coding', 'research', 'security', 'audit', 'verification']

export default function AegisChat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [purpose, setPurpose] = useState('general')
  const [busy, setBusy] = useState(false)
  const [reply, setReply] = useState<Reply | null>(null)

  async function submit(event: FormEvent) {
    event.preventDefault()
    const text = input.trim()
    if (!text || busy) return
    const next = [...messages, { role: 'user' as const, content: text }]
    setMessages(next)
    setInput('')
    setBusy(true)
    setReply(null)
    try {
      const response = await fetch('/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ messages: next, purpose, local_only: true, allow_external: false, metadata: { interface: 'aegis-control-center' } }) })
      const data: Reply = await response.json()
      if (!response.ok || !data.ok || !data.response) throw new Error(data.error || 'AEGIS could not complete the request')
      setReply(data)
      setMessages(current => [...current, { role: 'assistant', content: data.response!.content }])
    } catch (error) {
      setReply({ ok: false, error: error instanceof Error ? error.message : 'Model runtime unavailable' })
    } finally { setBusy(false) }
  }

  return <section className="chat-layout">
    <div className="card chat-card">
      <div className="chat-head"><div><div className="eyebrow">AEGIS Intelligence</div><h2>Command conversation</h2><div className="muted">Requests stay inside the governed local model fabric.</div></div><label className="purpose">Purpose<select value={purpose} onChange={e => setPurpose(e.target.value)} disabled={busy}>{purposes.map(p => <option key={p}>{p}</option>)}</select></label></div>
      <div className="messages">{messages.length === 0 ? <div className="chat-empty"><strong>AEGIS is ready.</strong><span>Ask a question, plan a task, inspect a system, or reason through a problem.</span></div> : messages.map((message, i) => <div className={`message ${message.role}`} key={`${message.role}-${i}`}><div className="message-label">{message.role === 'user' ? 'YOU' : 'AEGIS'}</div><div>{message.content}</div></div>)}{busy && <div className="message assistant"><div className="message-label">AEGIS</div><div className="typing">Routing → inference → evidence → verification…</div></div>}</div>
      <form className="chat-form" onSubmit={submit}><textarea value={input} onChange={e => setInput(e.target.value)} rows={3} maxLength={12000} placeholder="Give AEGIS an instruction or question…" disabled={busy} /><button className="primary" disabled={!input.trim() || busy}>{busy ? 'Processing…' : 'Send to AEGIS'}</button></form>
    </div>
    <div className="card"><div className="eyebrow">Execution transparency</div><div className="row"><span>Routing</span><span className="badge">GOVERNED</span></div><div className="row"><span>Network policy</span><span className="badge">LOCAL ONLY</span></div><div className="row"><span>Evidence</span><span className="badge">RECORDED</span></div><div className="row"><span>Response check</span><span className="badge">NON-EMPTY</span></div>{reply?.ok && reply.route && <div className="route"><div className="eyebrow">Selected route</div><strong>{reply.route.model}</strong><div className="muted">{reply.route.provider} · {reply.timing_ms} ms</div><p className="muted">{reply.route.reason}</p></div>}{reply?.error && <div className="notice">{reply.error}</div>}</div>
  </section>
}
