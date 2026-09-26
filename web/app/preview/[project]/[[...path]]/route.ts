import { realpath, readFile } from 'node:fs/promises'
import path from 'node:path'
import { NextResponse } from 'next/server'

export const dynamic = 'force-dynamic'

const PROJECT_RE = /^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/
const ALLOWED_FILES = new Set(['.html', '.css', '.js', '.json', '.webmanifest', '.svg', '.png', '.jpg', '.jpeg', '.webp', '.ico'])
const CONTENT_TYPES: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.webmanifest': 'application/manifest+json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.webp': 'image/webp',
  '.ico': 'image/x-icon',
}

function previewRoot() {
  return path.resolve(process.env.AEGIS_PREVIEW_ROOT || path.join(process.cwd(), '..', '.jarvis', 'builds'))
}

async function containedFile(project: string, requestedPath: string[]) {
  if (!PROJECT_RE.test(project) || requestedPath.some(part => !part || part === '.' || part === '..' || part.includes('\\'))) return null
  const root = await realpath(previewRoot())
  const candidate = path.resolve(root, project, ...(requestedPath.length ? requestedPath : ['index.html']))
  if (candidate !== root && !candidate.startsWith(`${root}${path.sep}`)) return null
  const actual = await realpath(candidate)
  if (actual !== root && !actual.startsWith(`${root}${path.sep}`)) return null
  const extension = path.extname(actual).toLowerCase()
  if (!ALLOWED_FILES.has(extension)) return null
  return { actual, extension }
}

export async function GET(_request: Request, { params }: { params: Promise<{ project: string; path?: string[] }> }) {
  try {
    const resolved = await params
    const file = await containedFile(resolved.project, resolved.path || [])
    if (!file) return NextResponse.json({ ok: false, error: 'preview file not found' }, { status: 404 })
    const content = await readFile(file.actual)
    const headers = new Headers({
      'Cache-Control': 'no-store',
      'X-Content-Type-Options': 'nosniff',
      'Content-Type': CONTENT_TYPES[file.extension] || 'application/octet-stream',
    })
    if (file.extension === '.html') {
      headers.set('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'self'")
    }
    return new Response(new Uint8Array(content), { status: 200, headers })
  } catch (error) {
    const code = error && typeof error === 'object' && 'code' in error ? error.code : ''
    if (code === 'ENOENT' || code === 'EACCES') return NextResponse.json({ ok: false, error: 'preview file not found' }, { status: 404 })
    return NextResponse.json({ ok: false, error: 'preview unavailable' }, { status: 503 })
  }
}
