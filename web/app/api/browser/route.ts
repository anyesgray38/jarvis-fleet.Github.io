import { timingSafeEqual } from 'node:crypto'
import { NextResponse } from 'next/server'
import { getChromiumControl } from '../../../lib/chromium-control'

export const dynamic = 'force-dynamic'

function enabled(): boolean {
  return process.env.AEGIS_BROWSER_CONTROL_ENABLED === 'true'
}

function authorizationFailure(request: Request): NextResponse | null {
  if (!enabled()) {
    return NextResponse.json({ ok: false, error: 'browser control is disabled' }, { status: 403 })
  }

  const expected = process.env.AEGIS_BROWSER_CONTROL_TOKEN
  if (!expected) {
    return NextResponse.json({ ok: false, error: 'browser control authorization is not configured' }, { status: 503 })
  }

  const provided = request.headers.get('authorization') || ''
  const expectedBytes = Buffer.from(`Bearer ${expected}`)
  const providedBytes = Buffer.from(provided)
  const valid = providedBytes.length === expectedBytes.length && timingSafeEqual(providedBytes, expectedBytes)
  if (!valid) {
    return NextResponse.json({ ok: false, error: 'unauthorized' }, { status: 401 })
  }
  return null
}

function bodyString(body: Record<string, unknown>, key: string): string {
  const value = body[key]
  return typeof value === 'string' ? value : ''
}

export async function GET(request: Request) {
  const failure = authorizationFailure(request)
  if (failure) return failure

  try {
    return NextResponse.json({ ok: true, ...(await getChromiumControl().status()) })
  } catch (error) {
    return NextResponse.json({ ok: false, error: error instanceof Error ? error.message : 'browser unavailable' }, { status: 503 })
  }
}

export async function POST(request: Request) {
  const failure = authorizationFailure(request)
  if (failure) return failure

  let body: Record<string, unknown>
  try {
    body = await request.json()
  } catch {
    return NextResponse.json({ ok: false, error: 'invalid JSON body' }, { status: 400 })
  }

  const action = bodyString(body, 'action')
  const control = getChromiumControl()
  try {
    if (action === 'goto') return NextResponse.json({ ok: true, ...(await control.goto(bodyString(body, 'url'))) })
    if (action === 'click') return NextResponse.json({ ok: true, ...(await control.click(bodyString(body, 'selector'))) })
    if (action === 'type') return NextResponse.json({ ok: true, ...(await control.type(bodyString(body, 'selector'), bodyString(body, 'text'))) })
    if (action === 'screenshot') return NextResponse.json({ ok: true, ...(await control.screenshot()) })
    if (action === 'disconnect') {
      await control.disconnect()
      return NextResponse.json({ ok: true, disconnected: true })
    }
    return NextResponse.json({ ok: false, error: 'unsupported browser action' }, { status: 400 })
  } catch (error) {
    return NextResponse.json({ ok: false, error: error instanceof Error ? error.message : 'browser action failed' }, { status: 503 })
  }
}
