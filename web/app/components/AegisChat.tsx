'use client'

import { FormEvent, useCallback, useEffect, useRef, useState } from 'react'

type SpeechRecognitionResultLike = { isFinal: boolean; [index: number]: { transcript: string } }
type SpeechRecognitionEventLike = Event & { resultIndex: number; results: { length: number; [index: number]: SpeechRecognitionResultLike } }
type SpeechRecognitionLike = {
  continuous: boolean
  interimResults: boolean
  lang: string
  onend: (() => void) | null
  onerror: ((event: Event & { error?: string }) => void) | null
  onresult: ((event: SpeechRecognitionEventLike) => void) | null
  start: () => void
  stop: () => void
}
type SpeechRecognitionConstructor = new () => SpeechRecognitionLike

declare global {
  interface Window {
    SpeechRecognition?: SpeechRecognitionConstructor
    webkitSpeechRecognition?: SpeechRecognitionConstructor
  }
}

type Message = { role: 'user' | 'assistant'; content: string }
type Reply = { ok: boolean; request_id?: string; route?: { provider: string; model: string; reason: string; score: number; constraints: Record<string, unknown> }; timing_ms?: number; response?: { content: string }; error?: string }
type AegisChatProps = { initialPurpose?: string; title?: string; subtitle?: string; context?: string }
type RuntimeHealth = { ready: boolean; default_model?: string | null; external_inference_enabled?: boolean; error?: string }

const purposes = ['general', 'planning', 'coding', 'research', 'security', 'audit', 'verification']

export default function AegisChat({ initialPurpose = 'general', title = 'Command conversation', subtitle = 'Requests stay inside the governed local model fabric.', context }: AegisChatProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [purpose, setPurpose] = useState(initialPurpose)
  const [busy, setBusy] = useState(false)
  const [reply, setReply] = useState<Reply | null>(null)
  const [runtimeHealth, setRuntimeHealth] = useState<RuntimeHealth | null>(null)
  const [listening, setListening] = useState(false)
  const [speaking, setSpeaking] = useState(false)
  const [voiceOutput, setVoiceOutput] = useState(true)
  const [voiceSupported, setVoiceSupported] = useState(false)
  const [voiceNotice, setVoiceNotice] = useState<string | null>(null)
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null)

  const refreshHealth = useCallback(async (signal?: AbortSignal) => {
    try {
      const response = await fetch('/api/chat', { cache: 'no-store', signal })
      const data = await response.json()
      if (!signal?.aborted) setRuntimeHealth({ ...data, ready: response.ok && data.ready === true })
    } catch {
      if (!signal?.aborted) setRuntimeHealth({ ready: false, error: 'Cannot reach the AEGIS model service.' })
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    void refreshHealth(controller.signal)
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') void refreshHealth(controller.signal)
    }, 30000)
    return () => { controller.abort(); window.clearInterval(timer) }
  }, [refreshHealth])

  useEffect(() => {
    setVoiceSupported(Boolean(window.SpeechRecognition || window.webkitSpeechRecognition))
    return () => {
      recognitionRef.current?.stop()
      window.speechSynthesis?.cancel()
    }
  }, [])

  function toggleListening() {
    if (listening) {
      recognitionRef.current?.stop()
      return
    }
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!Recognition) {
      setVoiceNotice('Voice recognition is not available in this browser.')
      return
    }
    const recognition = new Recognition()
    recognition.continuous = false
    recognition.interimResults = false
    recognition.lang = navigator.language || 'en-US'
    recognition.onresult = event => {
      const transcript = Array.from({ length: event.results.length - event.resultIndex }, (_, offset) => event.results[event.resultIndex + offset])
        .filter(result => result?.isFinal)
        .map(result => result[0]?.transcript || '')
        .join(' ')
        .trim()
      if (transcript) setInput(current => `${current}${current ? ' ' : ''}${transcript}`)
    }
    recognition.onerror = event => {
      setListening(false)
      setVoiceNotice(event.error === 'not-allowed' ? 'Microphone permission was denied.' : `Voice recognition error: ${event.error || 'unknown error'}`)
    }
    recognition.onend = () => setListening(false)
    recognitionRef.current = recognition
    setVoiceNotice('Listening… speak your instruction.')
    setListening(true)
    try {
      recognition.start()
    } catch {
      setListening(false)
      setVoiceNotice('Voice recognition could not start. Try again.')
    }
  }

  function speak(text: string) {
    if (!voiceOutput || !('speechSynthesis' in window)) return
    window.speechSynthesis.cancel()
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.lang = navigator.language || 'en-US'
    utterance.onstart = () => setSpeaking(true)
    utterance.onend = () => setSpeaking(false)
    utterance.onerror = () => setSpeaking(false)
    window.speechSynthesis.speak(utterance)
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    const text = input.trim()
    if (!text || busy || !runtimeHealth?.ready) return
    const next = [...messages, { role: 'user' as const, content: text }]
    setMessages(next)
    setInput('')
    setBusy(true)
    setReply(null)
    setVoiceNotice(null)
    window.speechSynthesis?.cancel()
    try {
      const requestMessages = context ? [{ role: 'system' as const, content: context }, ...next] : next
      const response = await fetch('/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ messages: requestMessages, purpose, local_only: true, allow_external: false, metadata: { interface: 'aegis-control-center', project: context ? 'shark-after-dark' : undefined } }) })
      const data: Reply = await response.json()
      if (!response.ok || !data.ok || !data.response) throw new Error(data.error || 'AEGIS could not complete the request')
      setReply(data)
      setMessages(current => [...current, { role: 'assistant', content: data.response!.content }])
      speak(data.response.content)
    } catch (error) {
      setReply({ ok: false, error: error instanceof Error ? error.message : 'Model runtime unavailable' })
    } finally { setBusy(false); void refreshHealth() }
  }

  return <section className="chat-layout">
    <div className="card chat-card">
      <div className="chat-head"><div><div className="eyebrow">AEGIS Intelligence</div><h2>{title}</h2><div className="muted">{subtitle}</div></div><label className="purpose">Purpose<select value={purpose} onChange={e => setPurpose(e.target.value)} disabled={busy}>{purposes.map(p => <option key={p}>{p}</option>)}</select></label></div>
      <div className="notice" role="status">
        {runtimeHealth === null ? 'Checking model availability…' : runtimeHealth.ready ? 'Model connected' : runtimeHealth.error || 'The selected model is not available yet.'}
        {runtimeHealth?.default_model && <div className="muted">{runtimeHealth.default_model}</div>}
        {runtimeHealth?.external_inference_enabled === false && <div className="muted">Self-hosted inference only. OpenAI inference is disabled.</div>}
        <button type="button" onClick={() => void refreshHealth()} disabled={busy}>Check connection</button>
      </div>
      <div className="messages">{messages.length === 0 ? <div className="chat-empty"><strong>{runtimeHealth?.ready ? 'Ask AEGIS a question.' : 'Waiting for the model connection.'}</strong><span>Your answer will appear here after the model responds.</span></div> : messages.map((message, i) => <div className={`message ${message.role}`} key={`${message.role}-${i}`}><div className="message-label">{message.role === 'user' ? 'YOU' : 'AEGIS'}</div><div>{message.content}</div></div>)}{busy && <div className="message assistant"><div className="message-label">AEGIS</div><div className="typing">Generating a response…</div></div>}</div>
      <form className="chat-form" onSubmit={submit}><textarea aria-label="Message to AEGIS" value={input} onChange={e => setInput(e.target.value)} rows={3} maxLength={12000} placeholder="Give AEGIS an instruction or question…" disabled={busy} /><div className="chat-actions"><button type="button" className={`voice-button${listening ? ' active' : ''}`} onClick={toggleListening} disabled={busy || !voiceSupported} aria-label={listening ? 'Stop voice recognition' : 'Start voice recognition'}>{listening ? '■ Stop' : '🎙 Speak'}</button><button className="primary" disabled={!input.trim() || busy || !runtimeHealth?.ready}>{busy ? 'Processing…' : 'Send to AEGIS'}</button></div></form>
    </div>
    <div className="card"><div className="eyebrow">Execution transparency</div><div className="row"><span>Routing</span><span className="badge">GOVERNED</span></div><div className="row"><span>Network policy</span><span className="badge">LOCAL ONLY</span></div><div className="row"><span>Evidence</span><span className="badge">RECORDED</span></div><div className="row"><span>Response check</span><span className="badge">NON-EMPTY</span></div><div className="row"><span>Voice input</span><span className={`badge${listening ? ' voice-live' : ''}`}>{!voiceSupported ? 'UNAVAILABLE' : listening ? 'LISTENING' : 'BROWSER MIC'}</span></div><div className="row"><span>Voice output</span><label className="voice-toggle"><input type="checkbox" checked={voiceOutput} onChange={event => setVoiceOutput(event.target.checked)} /> {speaking ? 'SPEAKING' : 'ENABLED'}</label></div>{voiceNotice && <div className="notice">{voiceNotice}</div>}<div className="muted voice-note">Speech recognition uses your browser microphone permission; recognized text follows the same Aegis chat and local-only policy.</div>{reply?.ok && reply.route && <div className="route"><div className="eyebrow">Selected route</div><strong>{reply.route.model}</strong><div className="muted">{reply.route.provider} · {reply.timing_ms} ms</div><p className="muted">{reply.route.reason}</p></div>}{reply?.error && <div className="notice">{reply.error}</div>}</div>
  </section>
}
