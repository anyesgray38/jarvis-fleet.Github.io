'use client'

import { FormEvent, useCallback, useEffect, useState } from 'react'

type Business = { business_id: string; business_name: string; address: string; phone: string; category: string; website: string; website_state: string; location_class: string; classification: string; score_reasons: string[]; opportunities: string[]; landing_page?: { build?: { status?: string }; project_dir?: string }; evidence: { source: string; observation: string; confidence: string }[] }
type Scan = { scan_id: string; request: { target: string }; summary: { businesses_discovered: number; landing_pages_generated: number; errors: number }; businesses: Business[]; errors: string[]; completed_at: string }

export default function ProspectingDashboard() {
  const [target, setTarget] = useState('US-19 Thomaston Georgia')
  const [category, setCategory] = useState('')
  const [maxResults, setMaxResults] = useState('10')
  const [generate, setGenerate] = useState('1')
  const [scan, setScan] = useState<Scan | null>(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    const response = await fetch('/api/prospects?businesses=1&min_score=0&limit=50', { cache: 'no-store' })
    const data = await response.json() as { businesses?: Business[]; error?: string }
    if (!response.ok) throw new Error(data.error || 'Prospecting runtime unavailable')
    const businesses = data.businesses || []
    if (businesses.length) setScan(current => current ? { ...current, businesses } : { scan_id: 'stored-prospects', request: { target: 'Stored prospects' }, summary: { businesses_discovered: businesses.length, landing_pages_generated: businesses.filter(item => item.landing_page?.build?.status === 'PASS').length, errors: 0 }, businesses, errors: [], completed_at: '' })
  }, [])

  useEffect(() => { void refresh().catch(error => setMessage(error instanceof Error ? error.message : 'Prospecting runtime unavailable')) }, [refresh])

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!target.trim() || busy) return
    setBusy(true)
    setMessage(null)
    try {
      const response = await fetch('/api/prospects', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'scan', target: target.trim(), category: category.trim(), max_results: Number(maxResults), generate_limit: Number(generate) }) })
      const data = await response.json() as { result?: Scan; error?: string }
      if (!response.ok || !data.result) throw new Error(data.error || 'Scan failed')
      setScan(data.result)
      setMessage(`Completed ${data.result.scan_id}: ${data.result.summary.businesses_discovered} evidence-backed candidate(s).`)
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Scan failed')
    } finally {
      setBusy(false)
    }
  }

  return <section className="prospecting-page">
    <div className="prospecting-intro"><div><div className="eyebrow">OUTBOUND · BUSINESS PROSPECTING</div><h1>Find the gap. Build the proof.</h1><p className="floor-lede">AEGIS discovers public business records, verifies corridor evidence, audits digital presence, classifies observable gaps, and prepares private concept pages. It does not claim ownership or contact a business.</p></div><div className="prospecting-state"><i className="dot" /><strong>RESEARCH + BUILD READY</strong><span>Evidence required at every stage</span></div></div>
    <form className="prospecting-form" onSubmit={submit}><label>Geographic target<input value={target} onChange={event => setTarget(event.target.value)} placeholder="US-19 Thomaston Georgia" /></label><label>Category <span className="optional">optional</span><input value={category} onChange={event => setCategory(event.target.value)} placeholder="auto repair, restaurants…" /></label><label>Max businesses<input type="number" min="1" max="30" value={maxResults} onChange={event => setMaxResults(event.target.value)} /></label><label>Concept pages<input type="number" min="0" max="3" value={generate} onChange={event => setGenerate(event.target.value)} /></label><button className="intake-button" type="submit" disabled={busy || !target.trim()}>{busy ? 'Scanning public sources…' : 'Run business scan'}</button></form>
    {message && <div className={message.startsWith('Completed') ? 'notice success' : 'notice'}>{message}</div>}
    {scan && <><div className="prospecting-summary"><Metric label="Businesses discovered" value={scan.summary.businesses_discovered} /><Metric label="Demos generated" value={scan.summary.landing_pages_generated} /><Metric label="Workflow errors" value={scan.summary.errors} /><Metric label="Evidence records" value={scan.businesses.reduce((total, item) => total + item.evidence.length, 0)} /></div><div className="prospect-list">{scan.businesses.map(business => <ProspectCard key={business.business_id} business={business} />)}</div>{scan.errors.length > 0 && <div className="card wide"><div className="eyebrow">Workflow issues</div>{scan.errors.map(error => <p className="intake-message" key={error}>{error}</p>)}</div>}</>}
    {!scan && <div className="card wide empty">No scan loaded. Run a bounded scan to populate evidence-backed prospects.</div>}
  </section>
}

function Metric({ label, value }: { label: string; value: number }) { return <div className="card prospect-metric"><span className="muted">{label}</span><strong>{value}</strong></div> }
function ProspectCard({ business }: { business: Business }) {
  return <article className="prospect-card"><div className="prospect-card-top"><div><div className="eyebrow">{business.location_class.replaceAll('_', ' ')}</div><h2>{business.business_name}</h2><p>{business.address || 'Address not verified'}{business.phone ? ` · ${business.phone}` : ''}</p></div><div className="prospect-classification"><strong>{business.classification.replaceAll('_', ' ')}</strong><span>evidence-backed classification</span></div></div><div className="prospect-tags"><span>{business.classification.replaceAll('_', ' ')}</span><span>Website: {business.website_state}</span>{business.category && <span>{business.category}</span>}</div><div className="prospect-reasons">{business.score_reasons.length ? business.score_reasons.slice(0, 4).map(reason => <p key={reason}>+ {reason}</p>) : <p>No observable gap recorded in the bounded audit.</p>}</div><div className="prospect-footer"><span>{business.evidence.length} evidence record(s)</span><span>{business.landing_page?.build?.status === 'PASS' ? 'Static preview verified' : business.landing_page ? 'Demo needs review' : 'No demo generated'}</span></div></article>
}
