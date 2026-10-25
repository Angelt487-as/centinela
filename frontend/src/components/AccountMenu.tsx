import { useRef } from 'react';
import { ChevronDown, KeyRound, LogOut, Settings2, ShieldCheck, UserRound } from 'lucide-react';
import { useAuth } from '../auth';
import { useTask } from '../api';
import { Notice } from './ui';

export default function AccountMenu() {
  const { user, logout } = useAuth(); const task = useTask(); const details = useRef<HTMLDetailsElement>(null);
  if (!user) return null;
  return <details className="account-menu" ref={details} onKeyDown={event => { if (event.key === 'Escape' && details.current) { details.current.open = false; details.current.querySelector('summary')?.focus(); } }}><summary className="account-trigger" aria-label="Menú de cuenta"><span className="user-avatar">{user.username.slice(0, 2).toUpperCase()}</span><span className="account-trigger-name">{user.username}<small>{user.role === 'administrador' ? 'Administrador' : 'Analista'}</small></span><ChevronDown size={14}/></summary><div className="account-popover"><div className="account-identity"><strong>{user.username}</strong><span><ShieldCheck size={14}/>{user.role === 'administrador' ? 'Administrador' : 'Analista'}</span></div><a href="#cuenta" onClick={() => { if (details.current) details.current.open = false; }}><KeyRound size={18}/>Cambiar contraseña</a>{user.role === 'administrador' && <a href="#usuarios" onClick={() => { if (details.current) details.current.open = false; }}><Settings2 size={18}/>Administrar usuarios</a>}<button disabled={task.busy} onClick={() => void task.run(logout)}><LogOut size={18}/>{task.busy ? 'Cerrando sesión…' : 'Cerrar sesión'}</button><Notice error>{task.error}</Notice></div></details>;
}
