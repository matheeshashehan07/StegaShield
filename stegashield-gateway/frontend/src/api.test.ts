import { afterEach, describe, expect, it, vi } from 'vitest'
import type { SupabaseClient } from '@supabase/supabase-js'
import { ApiError, checkResponse, createApi, validateDocx } from './api'

afterEach(() => vi.unstubAllGlobals())

function client(userId: string | null = 'alice') {
  return { auth: { getSession: vi.fn().mockResolvedValue({ data: { session: userId ? { user: { id: userId }, access_token: 'user-access-token' } : null }, error: null }) } } as unknown as SupabaseClient
}

describe('authenticated API transport', () => {
  it('attaches the user JWT without changing a multipart content type', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response('{}'))
    vi.stubGlobal('fetch', fetch)
    const data = new FormData(); data.append('file', new File(['x'], 'a.docx'))
    await createApi(client(), 'alice').request('/documents', { method: 'POST', body: data })
    const [url, options] = fetch.mock.calls[0]
    expect(url).toBe('/api/v1/documents')
    expect(options.headers.get('Authorization')).toBe('Bearer user-access-token')
    expect(options.headers.has('Content-Type')).toBe(false)
    expect(options.body).toBe(data)
  })
  it.each([null, 'bob'])('rejects absent or changed user session: %s', async id => {
    const fetch = vi.fn(); vi.stubGlobal('fetch', fetch)
    await expect(createApi(client(id), 'alice').request('/documents')).rejects.toMatchObject({ status: 401 })
    expect(fetch).not.toHaveBeenCalled()
  })
  it('discards a response received after sign out', async () => {
    const auth = client()
    vi.mocked(auth.auth.getSession).mockResolvedValueOnce({ data: { session: { user: { id: 'alice' }, access_token: 'token' } }, error: null } as never).mockResolvedValueOnce({ data: { session: null }, error: null })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{"secret":"old-account"}')))
    await expect(createApi(auth, 'alice').request('/admin/users')).rejects.toBeInstanceOf(ApiError)
  })
  it('does not retry an unsafe POST after network failure', async () => {
    const fetch = vi.fn().mockRejectedValue(new TypeError('network'))
    vi.stubGlobal('fetch', fetch)
    await expect(createApi(client(), 'alice').request('/documents/id/download', { method: 'POST' })).rejects.toThrow('Cannot reach')
    expect(fetch).toHaveBeenCalledTimes(1)
  })
  it('preserves authorization errors as failures', async () => {
    await expect(checkResponse(new Response('{"detail":"Access denied."}', { status: 403 }))).rejects.toMatchObject({ status: 403, message: 'Access denied.' })
  })
})

describe('file selection', () => {
  it('accepts PDF only when enabled and still enforces size and extension', () => {
    expect(validateDocx(new File(['x'], 'Policy.PDF'), true)).toBeNull()
    expect(validateDocx(new File(['x'], 'Policy.PDF'), false)).toBeTruthy()
    expect(validateDocx(new File([], 'empty.pdf'), true)).toBeTruthy()
    expect(validateDocx(new File(['x'], 'file.exe'), true)).toBeTruthy()
    expect(validateDocx(new File([new Uint8Array(10 * 1024 * 1024 + 1)], 'large.pdf'), true)).toBeTruthy()
  })
  it('accepts a non-empty DOCX independent of browser MIME', () => {
    expect(validateDocx(new File(['x'], 'Policy.DOCX', { type: 'text/plain' }))).toBeNull()
  })
  it('rejects empty, missing, or unsupported files', () => {
    expect(validateDocx(undefined)).toBeTruthy()
    expect(validateDocx(new File([], 'empty.docx'))).toBeTruthy()
    expect(validateDocx(new File(['x'], 'file.pdf'))).toBeTruthy()
  })
  it('rejects files above the upload limit', () => {
    expect(validateDocx(new File([new Uint8Array(10 * 1024 * 1024 + 1)], 'large.docx'))).toBeTruthy()
  })
})
