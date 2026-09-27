import { expect, test, type Page } from '@playwright/test'
import JSZip from 'jszip'

const user = '10000000-0000-4000-8000-000000000001'
const doc = '20000000-0000-4000-8000-000000000001'
// Browser tests exercise real React/Supabase SDK code with explicit HTTP fixtures.
// Backend JWT, DOCX, and RLS correctness have separate Python/pgTAP suites.
async function setup(page: Page, role = 'admin', pdfEnabled = false) {
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname
    const method = route.request().method()
    let body: unknown = []
    if (path.endsWith('/auth/config')) body = { url: 'https://example.supabase.co', publishableKey: 'sb_publishable_test', supportedFormats: pdfEnabled ? ['docx', 'pdf'] : ['docx'] }
    else {
      expect(route.request().headers().authorization).toMatch(/^Bearer /)
      if (path.endsWith('/auth/me')) body = { id: user, role }
      else if (path.endsWith('/auth/profile/photo')) return route.fulfill({ status: 204 })
      else if (path.endsWith('/auth/profile')) body = { id: user, role, display_name: 'Test member', created_at: '2026-09-01T00:00:00Z' }
      else if (path.endsWith('/forensics/docx') || path.endsWith('/forensics/pdf')) body = { outcome: 'inconclusive', reason: 'document_bytes_changed' }
      else if (path.endsWith('/admin/users')) body = [{ id: user, display_name: 'Test member', role: 'user' }]
      else if (path.endsWith('/admin/positions')) body = [{ id: '50000000-0000-4000-8000-000000000001', name: 'Manager' }]
      else if (path.endsWith('/documents') && method === 'GET') body = [{ id: doc, title: 'Internal security policy', format: 'docx', size_bytes: 24576, created_at: '2026-09-05T12:00:00Z', original_filename: 'original.docx' }]
      else if (path.endsWith('/documents') && method === 'POST') body = { id: doc }
      else if (path.endsWith('/download')) {
        return route.fulfill({ status: 200, contentType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', body: Buffer.from('test-download-fixture') })
      }
    }
    await route.fulfill({ json: body })
  })
  await page.route('https://example.supabase.co/auth/v1/**', async route => {
    if (route.request().url().includes('/logout')) return route.fulfill({ status: 204 })
    const payload = Buffer.from(JSON.stringify({ sub: user, exp: Math.floor(Date.now() / 1000) + 3600, role: 'authenticated' })).toString('base64url')
    await route.fulfill({ json: { access_token: `eyJhbGciOiJIUzI1NiJ9.${payload}.test`, refresh_token: 'test-refresh', token_type: 'bearer', expires_in: 3600, user: { id: user, email: 'admin@example.com', app_metadata: {}, user_metadata: { role: 'admin' }, aud: 'authenticated', created_at: '2026-09-05T00:00:00Z' } } })
  })
  await page.goto('/')
  await page.getByLabel('Email address').fill('admin@example.com')
  await page.getByLabel('Password', { exact: true }).fill('test-only-password')
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'A secure home for your documents.' })).toBeVisible()
}

test('admin can navigate upload, access and forensic flows', async ({ page }) => {
  await setup(page)
  await expect(page.getByText('Internal security policy', { exact: true })).toBeVisible()
  await page.screenshot({ path: 'test-results/desktop-workspace.png', fullPage: true })
  await page.getByRole('button', { name: 'Access', exact: true }).click()
  await expect(page.getByRole('region', { name: 'Document access' })).toBeVisible()
  await page.getByLabel('Choose a member').selectOption(user)
  await page.getByRole('button', { name: 'Grant access' }).click()
  await page.getByRole('navigation').getByRole('button', { name: 'Upload original' }).click()
  await page.getByLabel('Document title').fill('Test policy')
  await page.getByLabel('Choose a DOCX document').setInputFiles({ name: 'policy.docx', mimeType: 'application/octet-stream', buffer: Buffer.from('test-file-fixture') })
  await page.getByRole('button', { name: 'Upload original', exact: true }).last().click()
  await expect(page.getByText('Original uploaded', { exact: true })).toBeVisible()
  await page.getByRole('navigation').getByRole('button', { name: 'Forensic lookup' }).click()
  await page.getByLabel('Choose a suspect DOCX').setInputFiles({ name: 'suspect.docx', mimeType: 'application/octet-stream', buffer: Buffer.from('test-file-fixture') })
  await page.getByRole('button', { name: 'Run forensic lookup' }).click()
  await expect(page.getByRole('heading', { name: 'Inconclusive' })).toBeVisible()
  await page.getByLabel('Choose a suspect DOCX').setInputFiles({ name: 'different.docx', mimeType: 'application/octet-stream', buffer: Buffer.from('different') })
  await expect(page.getByRole('heading', { name: 'Inconclusive' })).not.toBeVisible()
})

test('member has no admin navigation and can download', async ({ page }) => {
  await setup(page, 'user')
  await expect(page.getByRole('button', { name: 'Upload original' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Forensic lookup' })).toHaveCount(0)
  const download = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Download', exact: true }).click()
  expect((await download).suggestedFilename()).toBe(`${doc}-protected.docx`)
  await page.getByRole('button', { name: 'Sign out' }).click()
  await expect(page.getByRole('heading', { name: 'Sign in to your workspace' })).toBeVisible()
  await expect(page.getByText('Internal security policy', { exact: true })).toHaveCount(0)
})

test('enabled PDF uploads and forensic requests use PDF endpoints', async ({ page }) => {
  await setup(page, 'admin', true)
  await page.getByRole('navigation').getByRole('button', { name: 'Upload original' }).click()
  await page.getByLabel('Document title').fill('PDF policy')
  await page.getByLabel('Choose a DOCX or PDF document').setInputFiles({ name: 'policy.pdf', mimeType: 'application/pdf', buffer: Buffer.from('PDF fixture') })
  await page.getByRole('button', { name: 'Upload original', exact: true }).last().click()
  await expect(page.getByText('Original uploaded', { exact: true })).toBeVisible()
  await page.getByRole('navigation').getByRole('button', { name: 'Forensic lookup' }).click()
  await page.getByLabel('Choose a suspect DOCX or PDF').setInputFiles({ name: 'suspect.pdf', mimeType: 'application/pdf', buffer: Buffer.from('PDF fixture') })
  const request = page.waitForRequest('**/api/v1/forensics/pdf')
  await page.getByRole('button', { name: 'Run forensic lookup' }).click()
  expect((await request).method()).toBe('POST')
  await expect(page.getByRole('heading', { name: 'Inconclusive' })).toBeVisible()
})

test('refresh preserves session and sign out clears it across refresh', async ({ page }) => {
  await setup(page, 'user')
  await page.reload()
  await expect(page.getByRole('heading', { name: 'A secure home for your documents.' })).toBeVisible()
  await page.getByRole('button', { name: 'Sign out' }).click()
  await expect(page.getByLabel('Email address')).toBeVisible()
  await page.reload()
  await expect(page.getByLabel('Email address')).toBeVisible()
})

test('preview issues a protected download and isolates DOCX rendering', async ({ page }) => {
  await setup(page, 'user')
  const archive = new JSZip()
  archive.file('[Content_Types].xml', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
  archive.file('_rels/.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
  archive.file('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Confidential preview fixture</w:t></w:r></w:p><w:sectPr/></w:body></w:document>')
  const fixture = await archive.generateAsync({ type: 'nodebuffer' })
  await page.route('**/api/v1/documents/*/download', route => route.fulfill({ contentType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', body: fixture }))
  const issued = page.waitForRequest('**/api/v1/documents/*/download')
  await page.getByRole('button', { name: 'Preview', exact: true }).click()
  expect((await issued).method()).toBe('POST')
  await expect(page.getByRole('dialog', { name: 'Document preview' })).toBeVisible()
  await expect(page.getByTitle('DOCX document preview')).toHaveAttribute('sandbox', 'allow-same-origin')
  await expect(page.frameLocator('iframe[title="DOCX document preview"]').getByText('Confidential preview fixture')).toBeVisible()
  await page.screenshot({ path: 'test-results/protected-preview.png', fullPage: true })
  await expect(page.getByRole('link', { name: 'Save this protected copy' })).toHaveAttribute('download', `${doc}-protected.docx`)
  await page.getByRole('button', { name: 'Close preview' }).click()
  await expect(page.getByRole('dialog')).toHaveCount(0)
})

test('admin can grant by position and assign a member separately', async ({ page }) => {
  await setup(page)
  await page.getByRole('button', { name: 'Access', exact: true }).click()
  await page.getByLabel('Choose a job position').selectOption('50000000-0000-4000-8000-000000000001')
  const grant = page.waitForRequest(r => r.url().endsWith('/position-permissions') && r.method() === 'POST')
  await page.getByRole('button', { name: 'Grant position access' }).click()
  expect((await grant).postDataJSON()).toEqual({ position_id: '50000000-0000-4000-8000-000000000001' })
  await page.getByText('Manage job positions and member assignments', { exact: true }).click()
  await page.getByLabel('Member to assign').selectOption(user)
  await page.getByLabel('Assigned position').selectOption('50000000-0000-4000-8000-000000000001')
  page.once('dialog', dialog => dialog.accept())
  const assignment = page.waitForRequest(r => r.url().endsWith(`/admin/users/${user}/position`) && r.method() === 'POST')
  await page.getByRole('button', { name: 'Save assignment' }).click()
  expect((await assignment).postDataJSON()).toEqual({ position_id: '50000000-0000-4000-8000-000000000001' })
  await expect(page.getByLabel('Choose a member')).toBeVisible()
})

test('member can view and close their account profile', async ({ page }) => {
  await setup(page, 'user')
  await page.getByRole('button', { name: 'View profile' }).click()
  const profile = page.getByRole('dialog', { name: 'Your profile' })
  await expect(profile.getByText(user, { exact: true })).toBeVisible()
  await expect(profile.getByText('Test member', { exact: true })).toBeVisible()
  await expect(profile.getByText('admin@example.com', { exact: true })).toBeVisible()
  await expect(profile.getByText('Member', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Close profile' }).click()
  await expect(profile).toHaveCount(0)
})

test('member edits only name and picture and sidebar refreshes', async ({ page }) => {
  await setup(page, 'user')
  let displayName = 'Test member'
  await page.route('**/api/v1/auth/profile', async route => {
    if (route.request().method() === 'POST') {
      const body = route.request().postData() || ''
      expect(body).toContain('name="display_name"')
      expect(body).toContain('Alice Updated')
      expect(body).toContain('name="photo"')
      expect(body).not.toContain('name="role"')
      expect(body).not.toContain('name="user_id"')
      displayName = 'Alice Updated'
      return route.fulfill({ status: 204 })
    }
    return route.fulfill({ json: { id: user, role: 'user', display_name: displayName, created_at: '2026-09-01T00:00:00Z' } })
  })
  await page.getByRole('button', { name: 'View profile' }).click()
  await page.getByRole('button', { name: 'Edit profile' }).click()
  await page.getByLabel('Display name', { exact: true }).fill('Alice Updated')
  await page.getByLabel('Profile picture', { exact: true }).setInputFiles({ name: 'avatar.png', mimeType: 'image/png', buffer: Buffer.from('image-fixture-backend-validates-separately') })
  await expect(page.getByRole('dialog').getByRole('textbox')).toHaveCount(1)
  await page.getByRole('button', { name: 'Save profile' }).click()
  await expect(page.getByText('Your profile has been updated.', { exact: true })).toBeVisible()
  await expect(page.locator('.sidebar-bottom')).toContainText('Alice Updated')
  await page.getByRole('button', { name: 'Close profile' }).click()
  await page.getByRole('button', { name: 'View profile' }).click()
  await expect(page.getByRole('dialog').getByText('Alice Updated', { exact: true })).toBeVisible()
})

test('mobile layout fits viewport', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await setup(page, 'user')
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390)
  await expect(page.getByRole('button', { name: 'Documents', exact: true })).toBeVisible()
  await page.screenshot({ path: 'test-results/mobile-workspace.png', fullPage: true })
})
