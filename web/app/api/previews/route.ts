import { readdir, stat } from 'node:fs/promises'
import path from 'node:path'
import { NextResponse } from 'next/server'

export const dynamic = 'force-dynamic'

function previewRoot() {
  return path.resolve(process.env.AEGIS_PREVIEW_ROOT || path.join(process.cwd(), '..', '.jarvis', 'builds'))
}

export async function GET() {
  const root = previewRoot()
  try {
    const entries = await readdir(root, { withFileTypes: true })
    const previews = await Promise.all(entries.filter(entry => entry.isDirectory()).map(async entry => {
      const project = path.join(root, entry.name)
      const files = (await readdir(project, { withFileTypes: true })).filter(file => file.isFile()).map(file => file.name).sort()
      const metadata = await stat(project)
      return {
        name: entry.name,
        kind: files.includes('app.webmanifest') ? 'app' : 'website',
        files,
        updated_at: metadata.mtime.toISOString(),
        url: `/preview/${encodeURIComponent(entry.name)}/index.html`,
      }
    }))
    previews.sort((left, right) => right.updated_at.localeCompare(left.updated_at))
    return NextResponse.json({ ok: true, previews })
  } catch (error) {
    const code = error && typeof error === 'object' && 'code' in error ? error.code : ''
    if (code === 'ENOENT') return NextResponse.json({ ok: true, previews: [] })
    return NextResponse.json({ ok: false, previews: [], error: 'preview directory unavailable' }, { status: 503 })
  }
}
