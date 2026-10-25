import { Component, lazy, Suspense, useEffect, useRef, useState, type ReactNode } from 'react';
import { Activity, ArrowUpRight, BookOpen, ChevronRight, Database, FileBadge2, Globe2, LayoutDashboard, LockKeyhole, MapPinned, Menu, Moon, Network, RefreshCw, ShieldCheck, Sun, UsersRound, X } from 'lucide-react';
import { AppContext } from './context';
import { api } from './api';
import type { Dataset, Overview, Resource } from './types';
import { Loading, Notice } from './components/ui';
import OverviewPage from './pages/Overview';
import { AuthProvider, useAuth } from './auth';
import Login from './pages/Login';
import AccountMenu from './components/AccountMenu';

const Analysis = lazy(() => import('./pages/Analysis'));
const Sources = lazy(() => import('./pages/Sources'));
const Geography = lazy(() => import('./pages/Geography'));
const Dossiers = lazy(() => import('./pages/Dossiers'));
const Users = lazy(() => import('./pages/Users'));
const Account = lazy(() => import('./pages/Account'));
const navigation = [
  { id: 'inicio', label: 'Vista general', icon: LayoutDashboard },
  { id: 'analisis', label: 'Análisis de datos', icon: Network, number: '01' },
  { id: 'fuentes', label: 'Fuentes abiertas', icon: Globe2, number: '02' },
  { id: 'geografia', label: 'Geolocalización', icon: MapPinned, number: '03' },
  { id: 'fichas', label: 'Fichas de identificación', icon: FileBadge2, number: '04' },
  { id: 'usuarios', label: 'Gestión de usuarios', icon: UsersRound },
];
const currentRoute = () => [...navigation.map(n => n.id), 'cuenta'].includes(window.location.hash.slice(1)) ? window.location.hash.slice(1) : 'inicio';

class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() { return this.state.failed ? <Notice error>El módulo no pudo cargarse. <button className="text-button" onClick={() => window.location.reload()}>Recargar la aplicación</button></Notice> : this.props.children; }
}

export default function App() {
  return <AuthProvider><AccessGate/></AuthProvider>;
}

function AccessGate() {
  const { user, checking } = useAuth();
  const returnTo = useRef('#inicio');
  useEffect(() => {
    if (checking) return;
    if (user) {
      if (window.location.hash === '#acceso') window.location.replace(returnTo.current);
      return;
    }
    const guard = () => {
      const requested = window.location.hash.slice(1);
      if ([...navigation.map(item => item.id), 'cuenta'].includes(requested)) returnTo.current = '#' + requested;
      if (window.location.hash !== '#acceso') window.history.replaceState(null, '', '#acceso');
    };
    guard(); window.addEventListener('hashchange', guard);
    return () => window.removeEventListener('hashchange', guard);
  }, [checking, user?.id]);
  if (checking) return <main className="auth-page"><div className="auth-container auth-checking"><img src="/centinela-logo.webp" width={100} height={100} alt="Centinela 360"/><Loading label="Verificando acceso…"/></div></main>;
  return user ? <Workspace key={user.id}/> : <Login/>;
}

function Workspace() {
  const { user } = useAuth();
  const [route, setRoute] = useState(currentRoute); const [theme, setTheme] = useState(() => localStorage.getItem('centinela-theme') || 'dark');
  const [datasets, setDatasets] = useState<Dataset[]>([]); const [resources, setResources] = useState<Resource[]>([]); const [overview, setOverview] = useState<Overview | null>(null);
  const [activeId, selectDataset] = useState(''); const [revision, setRevision] = useState(0); const [error, setError] = useState(''); const [connected, setConnected] = useState(false);
  const drawer = useRef<HTMLDialogElement>(null); const help = useRef<HTMLDialogElement>(null); const heading = useRef<HTMLElement>(null);
  useEffect(() => { document.documentElement.dataset.theme = theme; localStorage.setItem('centinela-theme', theme); }, [theme]);
  useEffect(() => { const onHash = () => { setRoute(currentRoute()); drawer.current?.close(); setTimeout(() => heading.current?.focus(), 0); }; window.addEventListener('hashchange', onHash); return () => window.removeEventListener('hashchange', onHash); }, []);
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([api<{ items: Dataset[] }>('/datasets', { signal: controller.signal }), api<{ items: Resource[] }>('/resources', { signal: controller.signal }), api<Overview>('/overview', { signal: controller.signal })]).then(([d, r, o]) => { setDatasets(d.items); setResources(r.items); setOverview(o); setConnected(true); setError(''); selectDataset(previous => d.items.some(x => x.id === previous) ? previous : d.items[0]?.id || ''); }).catch(e => { if (e.name !== 'AbortError') { setError(e.message); setConnected(false); } });
    return () => controller.abort();
  }, [revision]);
  const Nav = () => <><a href="#inicio" className="brand" aria-label="Centinela 360, vista general"><img src="/centinela-logo.webp" width="54" height="54" alt="Logotipo de Centinela 360"/><span>Centinela<span className="brand-360">360</span><small>CENTRO DE ANÁLISIS</small></span></a><div className="nav-section-label">ESPACIO DE TRABAJO</div><nav aria-label="Navegación principal">{navigation.filter(item => item.id !== 'usuarios' || user?.role === 'administrador').map(({ id, icon: Icon, label, number }) => <a href={'#' + id} key={id} className={`nav-item ${route === id ? 'active' : ''}`} aria-current={route === id ? 'page' : undefined} onClick={() => drawer.current?.close()}><Icon size={20}/><span>{label}</span>{number && <small>{number}</small>}</a>)}</nav><div className="sidebar-bottom"><div className="secure-panel"><ShieldCheck size={23}/><div><strong>Entorno local</strong><p>Tus archivos, en tu equipo.</p></div></div><button className="nav-item" onClick={() => { drawer.current?.close(); help.current?.showModal(); }}><BookOpen size={19}/><span>Guía de uso</span><ArrowUpRight size={16}/></button><div className="sidebar-version">CENTINELA 360 <span>MVP · v1.1</span></div></div></>;
  const title = navigation.find(n => n.id === route)?.label || 'Mi cuenta';
  return <AppContext.Provider value={{ datasets, resources, overview, activeId, selectDataset, revision, refresh: () => setRevision(v => v + 1) }}><a className="skip-link" href="#contenido" onClick={e => { e.preventDefault(); heading.current?.focus(); }}>Saltar al contenido</a><div className="app-shell"><aside className="sidebar"><Nav/></aside><dialog ref={drawer} className="nav-dialog" aria-label="Menú de navegación"><button className="icon-button drawer-close" aria-label="Cerrar menú" onClick={() => drawer.current?.close()}><X/></button><Nav/></dialog><div className="workspace"><header className="topbar"><div className="topbar-left"><button className="icon-button menu-button" aria-label="Abrir menú" onClick={() => drawer.current?.showModal()}><Menu/></button><span className="breadcrumb">Espacio de trabajo <ChevronRight size={14}/> <strong>{title}</strong></span></div><div className="topbar-right"><span className={`connection-status ${connected ? '' : 'offline'}`}><span/>{connected ? 'Servidor conectado' : 'Sin conexión'}</span><button className="icon-button" aria-label={theme === 'dark' ? 'Activar modo claro' : 'Activar modo oscuro'} onClick={() => setTheme(t => t === 'dark' ? 'light' : 'dark')}>{theme === 'dark' ? <Sun size={20}/> : <Moon size={20}/>}</button><AccountMenu/></div></header><main id="contenido" tabIndex={-1} ref={heading}>{error && <Notice error>{error} <button className="text-button" onClick={() => setRevision(v => v + 1)}><RefreshCw size={16}/>Reintentar conexión</button></Notice>}<ErrorBoundary key={route}><Suspense fallback={<Loading label="Abriendo módulo…"/>}>{route === 'inicio' ? <OverviewPage/> : route === 'analisis' ? <Analysis/> : route === 'fuentes' ? <Sources/> : route === 'geografia' ? <Geography/> : route === 'fichas' ? <Dossiers/> : route === 'usuarios' ? (user?.role === 'administrador' ? <Users/> : <Notice error>No tienes permiso para administrar usuarios.</Notice>) : <Account/>}</Suspense></ErrorBoundary><footer className="workspace-footer"><span><LockKeyhole size={14}/>Uso local y autorizado</span><span>Centinela 360 · Análisis con trazabilidad</span></footer></main></div></div><dialog ref={help} className="help-dialog" aria-labelledby="help-title"><div className="section-heading"><h2 id="help-title">Comienza con Centinela 360</h2><button className="icon-button" aria-label="Cerrar guía" onClick={() => help.current?.close()}><X/></button></div><ol className="guide-list"><li><strong>Importa un archivo.</strong> En Análisis de datos, selecciona CSV, XLS o XLSX, o usa un recurso del hackathon. Revisa los avisos de importación.</li><li><strong>Consulta y filtra.</strong> Explora eventos y vínculos. Geolocalización utiliza las coordenadas disponibles del mismo archivo.</li><li><strong>Conserva evidencias.</strong> Registra una URL pública y adjunta archivos. El sistema calcula su SHA-256 sin visitar automáticamente la URL.</li><li><strong>Revisa una ficha.</strong> Importa PDF o Word, edita los campos y guarda el progreso. Confirma la revisión humana para exportar.</li></ol><Notice>Los mapas base externos se activan bajo tu control. Las líneas cronológicas no representan recorridos GPS. Los documentos escaneados sin texto requieren OCR externo.</Notice><button className="button primary" onClick={() => help.current?.close()}>Entendido</button></dialog></AppContext.Provider>;
}
