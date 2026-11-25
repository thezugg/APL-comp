export async function api<T>(path: string, method = 'GET', body?: unknown, csrf?: string): Promise<T> {
  const headers: Record<string, string> = {}
  if (csrf && method !== 'GET') headers['X-CSRF-Token'] = csrf
  if (body !== undefined) headers['Content-Type'] = typeof body === 'string' ? 'text/csv; charset=utf-8' : 'application/json'
  const response = await fetch(path, {
    method,
    credentials: 'same-origin',
    headers,
    body: body === undefined ? undefined : typeof body === 'string' ? body : JSON.stringify(body),
  })
  if (!response.ok) {
    const data = await response.json().catch(() => ({})) as { detail?: string | { msg?: string }[] }
    const details = Array.isArray(data.detail) ? data.detail.map(x => x.msg).join(', ') : data.detail
    throw new Error(details || `Request failed (${response.status})`)
  }
  return response.json() as Promise<T>
}
