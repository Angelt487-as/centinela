import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { api, ApiError, jsonBody, setCsrfToken } from './api';

export type User = { id: string; username: string; role: 'administrador' | 'analista'; active: boolean; created_at: string; last_login: string | null };
export type AuthSession = { user: User; csrf_token: string; expires_at: number };
export type LoginChallenge = { csrf_token: string; setup_required: boolean };
type AuthContextValue = { user: User | null; checking: boolean; notice: string; login: (username: string, password: string) => Promise<void>; logout: () => Promise<void>; refresh: () => Promise<void>; endSession: (message?: string, broadcast?: boolean) => void };
const AuthContext = createContext<AuthContextValue | null>(null);
export const useAuth = () => { const value = useContext(AuthContext); if (!value) throw new Error('Contexto de sesión no disponible.'); return value; };

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<AuthSession | null>(null); const [checking, setChecking] = useState(true); const [notice, setNotice] = useState('');
  const channel = useRef<BroadcastChannel | null>(null); const user = useRef<User | null>(null);
  const endSession = useCallback((message = '', broadcast = false) => { setCsrfToken(''); user.current = null; setSession(null); setNotice(message); setChecking(false); if (broadcast) channel.current?.postMessage('logout'); }, []);
  const accept = useCallback((value: AuthSession) => { setCsrfToken(value.csrf_token); user.current = value.user; setSession(value); setNotice(''); }, []);
  const refresh = useCallback(async (signal?: AbortSignal) => {
    try { accept(await api<AuthSession>('/auth/session', { signal })); }
    catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') return;
      endSession(error instanceof ApiError && error.status === 401 ? (user.current ? 'Tu sesión terminó. Inicia sesión nuevamente.' : '') : 'No se pudo comprobar la sesión. Verifica que el servidor local esté iniciado.');
    } finally { if (!signal?.aborted) setChecking(false); }
  }, [accept, endSession]);
  useEffect(() => {
    const controller = new AbortController(); void refresh(controller.signal);
    const expired = () => endSession('Tu sesión terminó. Inicia sesión nuevamente.');
    const deadline = (event: Event) => { const value = (event as CustomEvent<number>).detail; setSession(current => current && current.expires_at !== value ? { ...current, expires_at: value } : current); };
    const focused = () => { if (user.current) void refresh(); };
    window.addEventListener('centinela:unauthorized', expired);
    window.addEventListener('centinela:session-deadline', deadline);
    window.addEventListener('focus', focused);
    if ('BroadcastChannel' in window) {
      channel.current = new BroadcastChannel('centinela-auth');
      channel.current.onmessage = event => { if (event.data === 'logout') expired(); else if (event.data === 'changed') void refresh(); };
    }
    return () => { controller.abort(); window.removeEventListener('centinela:unauthorized', expired); window.removeEventListener('centinela:session-deadline', deadline); window.removeEventListener('focus', focused); channel.current?.close(); channel.current = null; };
  }, [endSession, refresh]);
  useEffect(() => {
    if (!session) return;
    const timer = setTimeout(() => endSession('Tu sesión caducó por seguridad. Inicia sesión nuevamente.'), Math.max(0, session.expires_at * 1000 - Date.now()));
    return () => clearTimeout(timer);
  }, [session?.expires_at, endSession]);
  async function login(username: string, password: string) {
    const challenge = await api<LoginChallenge>('/auth/csrf');
    const value = await api<AuthSession>('/auth/login', { ...jsonBody({ username, password }), headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': challenge.csrf_token } });
    accept(value); channel.current?.postMessage('changed');
  }
  async function logout() {
    try { await api('/auth/logout', { method: 'POST' }); }
    catch (error) { if (!(error instanceof ApiError && error.status === 401)) throw error; }
    endSession('Sesión cerrada correctamente.'); channel.current?.postMessage('logout');
  }
  return <AuthContext.Provider value={{ user: session?.user || null, checking, notice, login, logout, refresh: () => refresh(), endSession }}>{children}</AuthContext.Provider>;
}
