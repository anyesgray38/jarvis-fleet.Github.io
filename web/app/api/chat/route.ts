import { NextResponse } from 'next/server'

export const dynamic = 'force-dynamic'

const runtime = process.env.AEGIS_MODEL_RUNTIME_URL?.replace(/\/$/, '') || 'http://127.0.0.1:8891'

export async function GET() {
  try {
    const response = await fetch(`${runtime}/health`, { cache: 'no-store', signal: AbortSignal.timeout(3000) })
    const data = await response.json().catch(() => ({}))
    return NextResponse.json({ connected: response.ok, ...data }, { status: response.ok ? 200 : 503 })
  } catch (error) {
    return NextResponse.json({ connected: false, error: error instanceof Error ? error.message : 'runtime unavailable' }, { status: 503 })
  }
}

export async function POST(req: Request) {
  let body: Record<string, unknown>
  try {
    body = await req.json()
  } catch {
    return NextResponse.json({ ok: false, error: 'invalid JSON body' }, { status: 400 })
  }

  const messages = body.messages
  if (!Array.isArray(messages) || messages.length === 0) {
    return NextResponse.json({ ok: false, error: 'messages are required' }, { status: 400 })
  }

  try {
    const response = await fetch(`${runtime}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        messages,
        purpose: typeof body.purpose === 'string' ? body.purpose : 'general',
        required_tags: Array.isArray(body.required_tags) ? body.required_tags : [],
        modality: typeof body.modality === 'string' ? body.modality : 'text',
        preferred_provider: typeof body.preferred_provider === 'string' ? body.preferred_provider : undefined,
        local_only: body.local_only !== false,
        allow_external: body.allow_external === true,
        metadata: typeof body.metadata === 'object' && body.metadata !== null ? body.metadata : {},
        temperature: typeof body.temperature === 'number' ? body.temperature : undefined,
        max_tokens: Number.isInteger(body.max_tokens) ? body.max_tokens : undefined,
      }),
      cache: 'no-store',
      signal: AbortSignal.timeout(125000),
    })
    const data = await response.json().catch(() => ({ ok: false, error: 'invalid runtime response' }))
    return NextResponse.json(data, { status: response.status })
  } catch (error) {
    return NextResponse.json({ ok: false, error: error instanceof Error ? error.message : 'model runtime unavailable' }, { status: 503 })
  }
}
