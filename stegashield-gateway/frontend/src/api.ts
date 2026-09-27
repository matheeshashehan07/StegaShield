import type { SupabaseClient } from '@supabase/supabase-js'

export type Identity = { id: string; role: 'user' | 'admin' }
export type DocumentRow = { id: string; title: string; original_filename: string; format: string; size_bytes: number; created_at: string }
export type Profile = Identity & { display_name: string | null }
export type Permission = { user_id: string; granted_at: string; expires_at: string | null }
export type ForensicResult = { outcome: 'inconclusive'; reason: string } | {
  outcome: 'matched'; exact_copy: true; message: string;
  download: { id: string; user_id: string; document_id: string; downloaded_at: string }
}
export type Audit = { id: string; attempt_id: string; outcome: string; reason: string; completed: boolean; attempted_at: string; performed_by: string }

export class ApiError extends Error {
  constructor(message: string, public status = 0) { super(message) }
}

export async function checkResponse(response: Response): Promise<Response> {
  if (response.ok) return response
  const body = await response.json().catch(() => ({}))
  const detail = typeof body.detail === 'string' ? body.detail : body.error?.message
  throw new ApiError(detail || (response.status === 422 ? 'Please check the information and file you submitted.' : 'The request could not be completed. Please try again.'), response.status)
}

export function createApi(auth: SupabaseClient, userId: string) {
  async function request(path: string, options: RequestInit = {}) {
    const { data, error } = await auth.auth.getSession()
    if (error || !data.session || data.session.user.id !== userId) throw new ApiError('Your session has ended. Please sign in again.', 401)
    const headers = new Headers(options.headers)
    headers.set('Authorization', `Bearer ${data.session.access_token}`)
    let response: Response
    try { response = await fetch(`/api/v1${path}`, { ...options, headers, cache: 'no-store' }) }
    catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') throw error
      throw new ApiError('Cannot reach the backend. Check that it is running and try again.')
    }
    const current = await auth.auth.getSession()
    if (current.data.session?.user.id !== userId) throw new ApiError('Your session changed. Please sign in again.', 401)
    return checkResponse(response)
  }
  return {
    request,
    async json<T>(path: string, options?: RequestInit): Promise<T> { return (await request(path, options)).json() },
  }
}
export type Api = ReturnType<typeof createApi>

export function validateDocx(file: File | undefined, pdfEnabled = false): string | null {
  if (!file) return 'Choose a DOCX file first.'
  if (!file.name.toLowerCase().endsWith('.docx') && !(pdfEnabled && file.name.toLowerCase().endsWith('.pdf'))) return pdfEnabled ? 'Only DOCX and PDF documents are supported.' : 'Only DOCX documents are supported.'
  if (file.size === 0 || file.size > 10 * 1024 * 1024) return 'Choose a non-empty file up to 10 MB.'
  return null
}

export const errorMessage = (error: unknown) => error instanceof Error ? error.message : 'Something went wrong. Please try again.'
export const dateLabel = (value: string) => new Date(value).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
