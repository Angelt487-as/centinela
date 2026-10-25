import { useMemo } from 'react';
import { ArrowRight, CheckCircle2, Database, FileBadge2, FileCheck2, FileText, Globe2, Layers3, MapPinned, Network, ShieldCheck, Upload } from 'lucide-react';
import { useWorkspace } from '../context';
import { useData } from '../api';
import type { Stats } from '../types';
import { dateTime, ImportPanel, Metric, number, Panel } from '../components/ui';

const modules = [
  { href: 'analisis', title: 'Análisis de datos', description: 'De registros originales a eventos y redes de vínculos.', icon: Network, tag: 'CSV · XLS · XLSX', className: 'blue' },
  { href: 'fuentes', title: 'Fuentes abiertas', description: 'Documenta fuentes públicas y conserva sus evidencias.', icon: Globe2, tag: 'URL · Evidencias · SHA-256', className: 'teal' },
  { href: 'geografia', title: 'Geolocalización', description: 'Explora conexiones a antenas en su contexto temporal.', icon: MapPinned, tag: 'Coordenadas · Cronología', className: 'purple' },
  { href: 'fichas', title: 'Fichas de identificación', description: 'Extrae, revisa y organiza información documental.', icon: FileBadge2, tag: 'PDF · Word · Revisión', className: 'amber' },
];
const actions: Record<string, string> = { datos_importados: 'Archivo de datos importado', fuente_registrada: 'Fuente pública registrada', evidencia_conservada: 'Evidencia conservada con SHA-256', ficha_importada: 'Documento de ficha importado', demostracion_creada: 'Demostración ficticia creada', borrador_guardado: 'Borrador de ficha guardado', ficha_revisada: 'Revisión humana confirmada' };

export default function OverviewPage() {
  const { overview: o, datasets, activeId, revision, resources } = useWorkspace();
  const { data: stats } = useData<Stats>(activeId ? '/stats?dataset_id=' + activeId : null, revision);
  const chart = useMemo(() => {
    const daily = stats?.daily || []; const size = Math.max(1, Math.ceil(daily.length / 60));
    const bars = [];
    for (let i = 0; i < daily.length; i += size) {
      const group = daily.slice(i, i + size);
      bars.push({ date: group.length === 1 ? group[0].date : `${group[0].date} — ${group[group.length - 1].date}`, count: group.reduce((sum, item) => sum + item.count, 0) });
    }
    return { bars, peak: Math.max(1, ...bars.map(b => b.count)) };
  }, [stats]);
  const current = datasets.find(d => d.id === activeId);
  return <><div className="page-heading overview-heading"><div><div className="eyebrow"><span className="eyebrow-line"/>PANORAMA GENERAL</div><h1>Centro de análisis</h1><p>Transforma documentos en información organizada y verificable.</p></div><a className="button primary" href="#analisis"><Upload size={18}/>Importar registros</a></div>
    <div className="welcome-band"><div className="welcome-symbol"><ShieldCheck size={34}/></div><div><strong>Un espacio de trabajo. Cuatro herramientas.</strong><p>Analiza datos, conserva evidencias y revisa documentos con trazabilidad.</p></div><span className="badge"><span className="status-dot"/>Procesamiento local</span></div>
    <div className="metrics-grid"><Metric label="Eventos importados" value={number(o?.events)} detail={`${number(o?.datasets)} archivos de datos`} icon={<Database size={20}/>}/><Metric label="Eventos geográficos" value={number(o?.geographic_events)} detail="Con coordenadas de la fuente" icon={<MapPinned size={20}/>} accent="teal"/><Metric label="Fuentes registradas" value={number(o?.sources)} detail={`${number(o?.evidence)} evidencias conservadas`} icon={<Globe2 size={20}/>} accent="purple"/><Metric label="Fichas de identificación" value={number(o?.dossiers)} detail="Borradores y fichas revisadas" icon={<FileBadge2 size={20}/>} accent="amber"/></div>
    <div className="section-heading modules-title"><div><h2>Herramientas de análisis</h2><p>Selecciona un módulo para comenzar o continuar tu trabajo.</p></div><span className="section-count">01 — 04</span></div>
    <div className="module-grid">{modules.map((m, i) => <a key={m.href} className={`module-card ${m.className}`} href={'#' + m.href}><div className="module-card-top"><span className="module-icon"><m.icon size={26}/></span><span className="module-number">0{i + 1}</span></div><h3>{m.title}</h3><p>{m.description}</p><div className="module-card-bottom"><span>{m.tag}</span><ArrowRight size={19}/></div></a>)}</div>
    {!datasets.length ? <ImportPanel/> : <div className="overview-bottom"><Panel><div className="section-heading"><div><h2><FileText size={19}/>Archivo de trabajo</h2><p>Resultados procedentes del documento importado.</p></div><span className="badge">Original conservado</span></div><div className="current-file"><span className="file-icon"><FileCheck2 size={26}/></span><div><strong>{current?.name}</strong><p>{number(current?.row_count)} eventos · {number(current?.metadata.coordinates)} con coordenadas</p></div></div>{stats && <div className="activity-chart"><div className="chart-heading"><span>Eventos por fecha</span><span>{stats.daily.length} días con registros</span></div><div className="mini-bars" role="img" aria-label={`Eventos diarios: ${chart.bars.map(d => `${d.date}: ${d.count}`).join('; ')}`}>{chart.bars.map(d => <span key={d.date} style={{ height: `${Math.max(5, d.count / chart.peak * 100)}%` }} title={`${d.date}: ${number(d.count)} eventos`}/>)}</div><div className="chart-axis"><span>{stats.first_event?.slice(0, 10)}</span><span>{stats.last_event?.slice(0, 10)}</span></div></div>}<a className="text-link" href="#analisis">Explorar este archivo<ArrowRight size={16}/></a></Panel><Panel><div className="section-heading"><div><h2>Actividad reciente</h2><p>Registro de operaciones del espacio local.</p></div><Layers3 size={19}/></div><ul className="activity-list">{o?.recent.map((item, i) => <li key={i}><span><CheckCircle2 size={16}/></span><div><strong>{actions[item.action] || 'Operación registrada'}</strong><small>{dateTime(item.created_at)}</small></div></li>)}</ul>{!o?.recent.length && <p className="muted">Las operaciones aparecerán aquí al comenzar.</p>}</Panel></div>}
    <div className="workspace-note"><ShieldCheck size={20}/><div><strong>La evidencia comienza en el original.</strong><p>{resources.length ? `${number(resources.length)} documentos disponibles en el ZIP local.` : 'Puedes importar tus propios archivos autorizados.'} Las demostraciones se identifican expresamente.</p></div></div>
  </>;
}
