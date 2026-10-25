import { useEffect, useRef, useState } from 'react';

let csrfToken = '';
export const setCsrfToken = (token: string) => { csrfToken = token; };
export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

async function request(path: string, options: RequestInit = {}) {
  const headers = new Headers(options.headers);
  if (!['GET', 'HEAD', 'OPTIONS'].includes((options.method || 'GET').toUpperCase()) && csrfToken && !headers.has('X-CSRF-Token')) headers.set('X-CSRF-Token', csrfToken);
  let response: Response;
  try { response = await fetch('/api' + path, { ...options, headers, credentials: 'same-origin' }); }
  catch (error) { if (error instanceof DOMException && error.name === 'AbortError') throw error; throw new Error('No se pudo conectar con el servidor local. Inicia el backend y vuelve a intentar.'); }
  const deadline = Number(response.headers.get('X-Session-Expires-At'));
  if (deadline) window.dispatchEvent(new CustomEvent('centinela:session-deadline', { detail: deadline }));
  if (!response.ok) {
    if (response.status === 401 && !['/auth/login', '/auth/session'].includes(path)) {
      csrfToken = '';
      window.dispatchEvent(new Event('centinela:unauthorized'));
    }
    const detail = await response.json().catch(() => ({}));
    throw new ApiError(typeof detail.detail === 'string' ? detail.detail : 'La operación no pudo completarse. Revisa los datos e intenta otra vez.', response.status);
  }
  return response;
}

export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await request(path, options);
  return response.json();
}
export const jsonBody = (value: unknown): RequestInit => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(value) });
export async function upload<T>(path: string, file: File): Promise<T> {
  if (file.size > 25 * 1024 * 1024) throw new Error('El archivo supera el límite de 25 MB.');
  const form = new FormData(); form.append('file', file);
  return api<T>(path, { method: 'POST', body: form });
}
export async function download(path: string, filename: string) {
  const response = await request(path);
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement('a'); link.href = url; link.download = filename; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export function useData<T>(path: string | null, revision = 0) {
  const [data, setData] = useState<T | null>(null);
  const previousPath = useRef<string | null>(null);
  const [error, setError] = useState(''); const [loading, setLoading] = useState(false);
  useEffect(() => {
    if (previousPath.current !== path) setData(null);
    previousPath.current = path; setError('');
    if (!path) { setLoading(false); return; }
    const controller = new AbortController(); setLoading(true);
    api<T>(path, { signal: controller.signal }).then(setData).catch(error => { if (error.name !== 'AbortError') setError(error.message); }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [path, revision]);
  return { data, error, loading };
}
export function useTask() {
  const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [message, setMessage] = useState('');
  async function run<T>(task: () => Promise<T>): Promise<T | undefined> {
    setBusy(true); setError(''); setMessage('');
    try { return await task(); } catch (e) { setError(e instanceof Error ? e.message : 'No se pudo completar la operación.'); }
    finally { setBusy(false); }
  }
  return { busy, error, message, setMessage, run };
}
