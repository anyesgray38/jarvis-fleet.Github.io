import { chromium, type Browser, type BrowserContext, type Locator, type Page } from 'playwright-core'

const DEFAULT_CDP_URL = 'http://127.0.0.1:9222'
const MAX_TYPE_CHARS = 2_000
const MAX_SELECTOR_CHARS = 500
const MAX_SCREENSHOT_BYTES = 4 * 1024 * 1024
const LOOPBACK_HOSTS = new Set(['127.0.0.1', 'localhost', '::1', '[::1]'])
const SENSITIVE_FIELD_PATTERN = /(password|passcode|one[-_ ]?time[-_ ]?code|otp|secret|api[-_ ]?key|access[-_ ]?token|refresh[-_ ]?token|credential)/i

export type BrowserStatus = {
  connected: boolean
  endpoint: string
  url: string
  title: string
  pages: number
}

export type BrowserScreenshot = {
  mimeType: 'image/png'
  width: number | null
  height: number | null
  imageBase64: string
}

function loopbackEndpoint(value: string): string {
  const endpoint = new URL(value)
  if (!['http:', 'https:'].includes(endpoint.protocol)) {
    throw new Error('CDP endpoint must use http or https')
  }
  if (!LOOPBACK_HOSTS.has(endpoint.hostname.toLowerCase())) {
    throw new Error('CDP endpoint must point to loopback')
  }
  if (endpoint.username || endpoint.password || endpoint.search || endpoint.hash) {
    throw new Error('CDP endpoint cannot contain credentials, query, or fragment')
  }
  return endpoint.toString().replace(/\/$/, '')
}

function navigationUrl(value: string): string {
  const target = new URL(value)
  const loopbackHttp = target.protocol === 'http:' && LOOPBACK_HOSTS.has(target.hostname.toLowerCase())
  if (target.protocol !== 'https:' && !loopbackHttp) {
    throw new Error('browser navigation allows HTTPS or loopback HTTP URLs only')
  }
  if (target.username || target.password) {
    throw new Error('browser navigation cannot contain credentials')
  }
  return target.toString()
}

function boundedSelector(value: unknown): string {
  if (typeof value !== 'string' || !value.trim()) throw new Error('selector is required')
  if (value.length > MAX_SELECTOR_CHARS) throw new Error('selector is too long')
  return value
}

async function one(locator: Locator, selector: string): Promise<Locator> {
  const count = await locator.count()
  if (count !== 1) throw new Error(`selector must match exactly one element: ${selector} (${count} matches)`)
  return locator
}

export class ChromiumControl {
  private browser: Browser | null = null
  private context: BrowserContext | null = null
  private page: Page | null = null
  private readonly endpoint: string
  private connecting: Promise<Browser> | null = null
  private operationTail: Promise<void> = Promise.resolve()
  private readonly guardedContexts = new WeakSet<BrowserContext>()

  constructor(endpoint = process.env.AEGIS_CHROME_CDP_URL || DEFAULT_CDP_URL) {
    this.endpoint = loopbackEndpoint(endpoint)
  }

  private async guard(context: BrowserContext): Promise<void> {
    if (this.guardedContexts.has(context)) return

    // Context routing covers existing pages and the first request of popup pages.
    await context.route('**/*', async route => {
      const request = route.request()
      const frame = request.frame()
      if (request.isNavigationRequest() && frame === frame.page().mainFrame()) {
        try {
          navigationUrl(request.url())
        } catch {
          await route.abort('blockedbyclient')
          return
        }
      }
      await route.continue()
    })
    this.guardedContexts.add(context)
  }

  private async connect(): Promise<Browser> {
    if (this.browser?.isConnected()) return this.browser
    if (this.browser) {
      this.browser = null
      this.context = null
      this.page = null
    }
    if (this.connecting) return this.connecting

    let connection: Promise<Browser>
    connection = chromium.connectOverCDP(this.endpoint, { timeout: 10_000 }).then(browser => {
      browser.on('disconnected', () => {
        if (this.browser === browser) {
          this.browser = null
          this.context = null
          this.page = null
        }
      })
      this.browser = browser
      return browser
    }).finally(() => {
      if (this.connecting === connection) this.connecting = null
    })
    this.connecting = connection
    return connection
  }

  private async currentPage(): Promise<Page> {
    const browser = await this.connect()
    if (!browser.isConnected()) throw new Error('CDP browser disconnected')

    if (!this.context || this.context.isClosed()) {
      this.context = browser.contexts()[0] || null
    }
    if (!this.context) {
      throw new Error('CDP browser has no default context')
    }
    await this.guard(this.context)

    if (!this.page || this.page.isClosed()) {
      const pages = this.context.pages().filter(page => !page.isClosed())
      this.page = pages[pages.length - 1] || await this.context.newPage()
    }
    return this.page
  }

  private async statusFrom(page: Page): Promise<BrowserStatus> {
    return {
      connected: true,
      endpoint: this.endpoint,
      url: page.url(),
      title: await page.title().catch(() => ''),
      pages: this.context?.pages().length || 0,
    }
  }

  private enqueue<T>(operation: () => Promise<T>): Promise<T> {
    const run = this.operationTail.then(operation, operation)
    this.operationTail = run.then(() => undefined, () => undefined)
    return run
  }

  async status(): Promise<BrowserStatus> {
    return this.enqueue(async () => this.statusFrom(await this.currentPage()))
  }

  async goto(url: string): Promise<BrowserStatus> {
    return this.enqueue(async () => {
      const page = await this.currentPage()
      await page.goto(navigationUrl(url), { waitUntil: 'domcontentloaded', timeout: 30_000 })
      return this.statusFrom(page)
    })
  }

  async click(selector: string): Promise<BrowserStatus> {
    return this.enqueue(async () => {
      const page = await this.currentPage()
      await (await one(page.locator(boundedSelector(selector)), selector)).click({ timeout: 10_000 })
      return this.statusFrom(page)
    })
  }

  async type(selector: string, text: string): Promise<BrowserStatus> {
    return this.enqueue(async () => {
      if (typeof text !== 'string' || !text || text.length > MAX_TYPE_CHARS) {
        throw new Error(`text must contain 1-${MAX_TYPE_CHARS} characters`)
      }
      const safeSelector = boundedSelector(selector)
      const page = await this.currentPage()
      const field = await one(page.locator(safeSelector), safeSelector)
      const metadata = await field.evaluate(element => ({
        type: element instanceof HTMLInputElement ? element.type.toLowerCase() : '',
        autocomplete: element.getAttribute('autocomplete')?.toLowerCase() || '',
        descriptor: [
          element.getAttribute('name'),
          element.id,
          element.getAttribute('aria-label'),
          element.getAttribute('role'),
        ].filter(Boolean).join(' ').toLowerCase(),
      }))
      if (metadata.type === 'password' || SENSITIVE_FIELD_PATTERN.test(`${metadata.autocomplete} ${metadata.descriptor}`)) {
        throw new Error('password and secret fields are blocked by AEGIS policy')
      }
      await field.fill(text)
      return this.statusFrom(page)
    })
  }

  async screenshot(): Promise<BrowserScreenshot> {
    return this.enqueue(async () => {
      const page = await this.currentPage()
      const image = await page.screenshot({ type: 'png', animations: 'disabled' })
      if (image.byteLength > MAX_SCREENSHOT_BYTES) {
        throw new Error(`screenshot exceeds ${MAX_SCREENSHOT_BYTES} bytes`)
      }
      const viewport = page.viewportSize()
      return {
        mimeType: 'image/png' as const,
        width: viewport?.width || null,
        height: viewport?.height || null,
        imageBase64: image.toString('base64'),
      }
    })
  }

  async disconnect(): Promise<void> {
    return this.enqueue(async () => {
      const browser = this.browser
      this.page = null
      this.context = null
      this.browser = null
      await browser?.close().catch(() => undefined)
    })
  }
}

let singleton: ChromiumControl | null = null

export function getChromiumControl(): ChromiumControl {
  if (!singleton) singleton = new ChromiumControl()
  return singleton
}
