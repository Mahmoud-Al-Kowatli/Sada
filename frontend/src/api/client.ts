// Thin API client: bearer token from localStorage, uniform {code, message} errors.
export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message)
  }
}

const BASE = '/api/v1'

export function getToken(): string | null {
  try { return localStorage.getItem('sada.token') } catch { return null }
}
export function setToken(t: string | null) {
  try { t ? localStorage.setItem('sada.token', t) : localStorage.removeItem('sada.token') } catch { /* private mode */ }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<{ data: T; status: number }> {
  const headers: Record<string, string> = { ...(init.headers as Record<string, string> | undefined) }
  if (!(init.body instanceof FormData)) headers['Content-Type'] = 'application/json'
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`
  const res = await fetch(BASE + path, { ...init, headers })
  const text = await res.text()
  const body = text ? JSON.parse(text) : null
  if (!res.ok) {
    if (res.status === 401) setToken(null)
    throw new ApiError(res.status, body?.code ?? 'HTTP_ERROR', body?.message ?? 'حدث خطأ غير متوقع')
  }
  return { data: body as T, status: res.status }
}

// ---- types (mirror backend schemas) ----
export interface User { user_id: string; full_name: string; email: string; roles: string[] }
export interface Account {
  account_id: string; account_number: string; currency: string
  available_balance: string; frozen_balance: string; daily_limit: string; daily_used: string; status: string
}
export interface Transfer {
  transfer_id: string; reference: string; amount: string; status: 'COMPLETED' | 'HELD' | 'CANCELLED'
  destination_account_number: string; destination_name: string | null; note: string | null
  created_at: string; completed_at: string | null; triggered_rules: string[]; case_reference: string | null
}
export interface Ticket {
  ticket_id: string; reference: string; request_type: string; description: string; status: string
  created_at: string; assessment_status: string | null; spoof_score: string | null; case_reference: string | null
}
export interface Precheck { ok: boolean; destination_name: string; otp_id: string; dev_otp_code: string | null }

export const fmtMoney = (v: string | number, currency = 'ر.س') =>
  `${Number(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${currency}`
export const fmtDate = (iso: string) =>
  new Date(iso).toLocaleString('ar-SA-u-nu-latn', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
