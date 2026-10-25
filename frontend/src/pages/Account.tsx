import { useState, type FormEvent } from 'react';
import { KeyRound, ShieldCheck } from 'lucide-react';
import { api, jsonBody, useTask } from '../api';
import { useAuth } from '../auth';
import { Field, Notice, Panel, TaskFeedback } from '../components/ui';

export default function Account() {
  const { user, endSession } = useAuth(); const task = useTask(); const [current, setCurrent] = useState(''); const [next, setNext] = useState(''); const [confirmation, setConfirmation] = useState(''); const [error, setError] = useState('');
  async function change(event: FormEvent) {
    event.preventDefault(); setError('');
    if (next !== confirmation) { setError('Las nuevas contraseñas no coinciden.'); return; }
    await task.run(async () => { await api('/auth/password', jsonBody({ current_password: current, new_password: next })); setCurrent(''); setNext(''); setConfirmation(''); endSession('Contraseña actualizada. Inicia sesión con tu nueva contraseña.', true); });
  }
  return <><div className="page-heading"><div><div className="eyebrow">MI CUENTA</div><h1>Cambiar contraseña</h1><p>Cuenta: {user?.username}</p></div></div><Panel className="password-panel"><div className="section-heading"><h2><KeyRound size={20}/>Actualizar datos de acceso</h2></div><Notice>Al cambiar la contraseña se cerrarán todas las sesiones de tu cuenta. Tendrás que iniciar sesión nuevamente.</Notice><form className="form-stack" onSubmit={change}><Field label="Contraseña actual"><input required type="password" autoComplete="current-password" value={current} onChange={e => setCurrent(e.target.value)}/></Field><Field label="Nueva contraseña" hint="Entre 12 y 128 caracteres; puedes usar una frase larga."><input required type="password" autoComplete="new-password" minLength={12} maxLength={128} value={next} onChange={e => setNext(e.target.value)}/></Field><Field label="Confirmar nueva contraseña"><input required type="password" autoComplete="new-password" minLength={12} maxLength={128} value={confirmation} onChange={e => setConfirmation(e.target.value)}/></Field><Notice error>{error}</Notice><button className="button primary" disabled={task.busy}><ShieldCheck size={18}/>Guardar nueva contraseña</button><TaskFeedback task={task}/></form></Panel></>;
}
