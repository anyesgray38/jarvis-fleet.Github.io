// Run against a dev server: AEGIS_TEST_URL=http://127.0.0.1:3001 node scripts/test-chat-ui.mjs
// Provider replies are deliberately mocked: this tests UI behavior, not real inference.
import assert from 'node:assert/strict'
import { chromium } from 'playwright-core'

const browser = await chromium.launch({
  executablePath: process.env.AEGIS_TEST_CHROMIUM,
  headless: true,
})
try {
  const page = await browser.newPage()
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  let ready = false
  let posted
  await page.route('**/api/chat', async route => {
    if (route.request().method() === 'GET') {
      await route.fulfill({ json: { ready, default_model: 'test-qwen', external_inference_enabled: false } })
    } else {
      posted = route.request().postDataJSON()
      await route.fulfill({ json: {
        ok: true, response: { content: 'Mock Qwen response for UI verification.' },
        route: { provider: 'localai', model: 'test-qwen', reason: 'Test fixture' }, timing_ms: 1,
      } })
    }
  })
  await page.goto(`${process.env.AEGIS_TEST_URL || 'http://127.0.0.1:3001'}/chat`, { waitUntil: 'domcontentloaded', timeout: 60000 })
  await page.getByText('The selected model is not available yet.').waitFor()
  assert.equal(await page.getByText('AEGIS is ready.', { exact: true }).count(), 0)
  await page.getByLabel('Message to AEGIS').fill('UI verification only')
  assert.equal(await page.getByRole('button', { name: 'Send to AEGIS' }).isDisabled(), true)
  ready = true
  await page.getByRole('button', { name: 'Check connection' }).click()
  await page.getByText('Model connected', { exact: false }).waitFor()
  await page.getByText('Self-hosted inference only. OpenAI inference is disabled.').waitFor()
  assert.equal(await page.getByRole('button', { name: 'Send to AEGIS' }).isEnabled(), true)
  await page.locator('.voice-toggle input').uncheck()
  await page.getByRole('button', { name: 'Send to AEGIS' }).click()
  await page.getByText('Mock Qwen response for UI verification.').waitFor()
  assert.equal(posted.local_only, true)
  assert.equal(posted.allow_external, false)
  await page.locator('.route').getByText('test-qwen', { exact: true }).waitFor()
  assert.deepEqual(errors, [])
  console.log('PASS: unavailable/ready states, send guard, self-hosted request, response and route display; mocked inference only.')
} finally {
  await browser.close()
}
