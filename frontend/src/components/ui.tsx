import { useEffect, useId, useRef, useState, type ReactNode, type FormEvent } from 'react';
import { AlertCircle, CheckCircle2, ChevronDown, FileUp, FolderOpen, LoaderCircle, Search, SlidersHorizontal, Upload, Database, ArrowRight, ShieldCheck } from 'lucide-react';
import { useWorkspace } from '../context';
import { api, upload, useTask } from '../api';
import type { Dataset, Dossier, Filters } from '../types';

export const number = (n: number | null | undefined) => new Intl.NumberFormat('es-MX').format(n ?? 0);
export const dateTime = (value?: string | null) => { if (!value) return 'No disponible'; if (/(?:Z|[+-][0-9]{2}:[0-9]{2})$/.test(value)) return new Intl.DateTimeFormat('es-MX', { timeZone: 'America/Mexico_City', dateStyle: 'short', timeStyle: 'medium' }).format(new Date(value)); const [date, time] = value.split('T'); const parts = date.split('-'); return `${parts[2]}/${parts[1]}/${parts[0]}${time ? ' · ' + time.substring(0, 8) : ' · sin hora'}`; };
export const dateOnly = (value?: string | null) => value ? dateTime(value.split('T')[0]).replace(' · sin hora', '') : 'Sin fecha';
export function Notice({ children, error = false, success = false }: { children: ReactNode; error?: boolean; success?: boolean }) { if (!children) return null; const Icon = success ? CheckCircle2 : AlertCircle; return <div className={`notice ${error ? 'error' : success ? 'success' : ''}`} role={error ? 'alert' : 'status'}><Icon size={20} aria-hidden="true"/><div>{children}</div></div>; }
export function Loading({ label = 'Cargando información…' }: { label?: string }) { return <div className="loading" role="status"><LoaderCircle size={22} className="spinner" aria-hidden="true"/>{label}</div>; }
export function Panel({ children, className = '' }: { children: ReactNode; className?: string }) { return <section className={`panel ${className}`}>{children}</section>; }
export function PageHeading({ number: step, title, description, actions }: { number: string; title: string; description: string; actions?: ReactNode }) { return <div className="page-heading"><div><div className="eyebrow">MÓDULO {step}</div><h1>{title}</h1><p>{description}</p></div>{actions && <div className="heading-actions">{actions}</div>}</div>; }
export function Empty({ title, children, icon = <Database size={30}/> }: { title: string; children: ReactNode; icon?: ReactNode }) { return <div className="empty"><div className="empty-icon" aria-hidden="true">{icon}</div><h3>{title}</h3><p>{children}</p></div>; }
export function Metric({ label, value, detail, icon, accent = '' }: { label: string; value: string; detail: string; icon: ReactNode; accent?: string }) { return <div className={`metric ${accent}`}><div className="metric-top"><span>{label}</span><span className="metric-icon" aria-hidden="true">{icon}</span></div><strong>{value}</strong><span className="metric-detail">{detail}</span></div>; }
export function Field({ label, children, hint, className = '' }: { label: string; children: ReactNode; hint?: string; className?: string }) { return <label className={`field ${className}`}><span>{label}</span>{children}{hint && <small>{hint}</small>}</label>; }
export function DatasetPicker() { const { datasets, activeId, selectDataset } = useWorkspace(); return <div className="dataset-picker"><Database size={18} aria-hidden="true"/><label><span>Archivo de trabajo</span><select aria-label="Archivo de trabajo" value={activeId} onChange={e => selectDataset(e.target.value)}>{!datasets.length && <option value="">Importa un archivo para comenzar</option>}{datasets.map(d => <option key={d.id} value={d.id}>{d.name} · {number(d.row_count)} eventos</option>)}</select></label></div>; }
export function TaskFeedback({ task }: { task: ReturnType<typeof useTask> }) { return <><Notice error>{task.error}</Notice><Notice success>{task.message}</Notice>{task.busy && <Loading label="Procesando el archivo. Conservamos el original…"/>}</>; }

export function ImportPanel({ mode = 'datos', onImported }: { mode?: 'datos' | 'fichas'; onImported?: (value: Dossier) => void }) {
  const { resources, refresh, selectDataset } = useWorkspace(); const task = useTask(); const input = useRef<HTMLInputElement>(null); const id = useId();
  const options = resources.filter(r => r.group === mode && (mode === 'fichas' || r.folder.includes('estructuracion'))).sort((a, b) => a.size - b.size);
  const [resource, setResource] = useState(''); const [dragging, setDragging] = useState(false);
  const selected = options.find(r => r.id === resource) || options[0];
  const path = mode === 'datos' ? '/datasets' : '/dossiers';
  async function imported(promise: Promise<Dataset | Dossier>) {
    const result = await task.run(() => promise);
    if (!result) return;
    if (mode === 'datos') { const d = result as Dataset; selectDataset(d.id); task.setMessage(d.duplicate ? 'Este archivo ya estaba importado. Se abrió sin duplicar sus eventos.' : `${number(d.row_count)} eventos importados desde el archivo original.`); }
    else { onImported?.(result as Dossier); task.setMessage('Texto extraído. Revisa los campos antes de exportar.'); }
    refresh();
  }
  function fileChosen(file?: File) { if (file) void imported(upload<Dataset | Dossier>(path + '/upload', file)); }
  return <Panel className="import-panel"><div className="section-heading"><div><h2><FileUp size={20} aria-hidden="true"/>Importar {mode === 'datos' ? 'registros' : 'documento'}</h2><p>Archivos originales, resultados verificables.</p></div><span className="badge neutral">Hasta 25 MB</span></div><div className="import-grid"><div className={`drop-zone ${dragging ? 'dragging' : ''}`} onDragOver={e => { e.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={e => { e.preventDefault(); setDragging(false); if (!task.busy) fileChosen(e.dataTransfer.files[0]); }}><Upload size={28} aria-hidden="true"/><strong>Arrastra un archivo aquí</strong><span>{mode === 'datos' ? 'CSV, XLS o XLSX' : 'PDF con texto o DOCX'}</span><input ref={input} id={id} className="sr-only" type="file" accept={mode === 'datos' ? '.csv,.xls,.xlsx' : '.pdf,.docx'} disabled={task.busy} aria-label={mode === 'datos' ? 'Seleccionar archivo de registros' : 'Seleccionar documento de ficha'} onChange={e => { fileChosen(e.target.files?.[0]); e.target.value = ''; }}/><button className="button secondary" onClick={() => input.current?.click()} disabled={task.busy}><FolderOpen size={17}/>Seleccionar archivo</button></div><div className="resource-import"><span className="eyebrow">DOCUMENTOS DISPONIBLES</span><h3>Usar los archivos del hackathon</h3><p>Se leen directamente del ZIP local. El original permanece intacto.</p><Field label="Recurso del proyecto"><select value={selected?.id || ''} onChange={e => setResource(e.target.value)} disabled={task.busy || !options.length}>{!options.length && <option>ZIP no disponible en esta instalación</option>}{options.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}</select></Field><button className="button primary" disabled={!selected || task.busy} onClick={() => selected && void imported(api<Dataset | Dossier>(path + '/resource/' + selected.id, { method: 'POST' }))}>Importar recurso <ArrowRight size={17}/></button></div></div><TaskFeedback task={task}/></Panel>;
}

export const emptyFilters: Filters = { number: '', kind: '', date_from: '', date_to: '' };
export function FilterBar({ kinds, onApply }: { kinds: string[]; onApply: (value: Filters) => void }) {
  const [values, setValues] = useState<Filters>(emptyFilters); const [error, setError] = useState('');
  const details = useRef<HTMLDetailsElement>(null);
  const [expanded, setExpanded] = useState(window.innerWidth >= 768);
  useEffect(() => {
    const workspace = details.current?.closest('.workspace');
    if (!workspace) return;
    let previous: boolean | undefined;
    const observer = new ResizeObserver(() => {
      const wide = workspace.clientWidth > 620;
      if (wide !== previous) { previous = wide; setExpanded(wide); }
    });
    observer.observe(workspace); return () => observer.disconnect();
  }, []);
  function apply(e: FormEvent) { e.preventDefault(); if (values.date_from && values.date_to && values.date_from > values.date_to) { setError('La fecha inicial debe ser anterior o igual a la final.'); return; } setError(''); onApply(values); }
  return <details className="filters" ref={details} open={expanded} onToggle={e => setExpanded(e.currentTarget.open)}><summary><SlidersHorizontal size={18}/>Filtros de consulta<ChevronDown size={16}/></summary><form onSubmit={apply} className="filter-grid"><Field label="Número"><input type="search" inputMode="tel" placeholder="Buscar número" value={values.number} onChange={e => setValues({ ...values, number: e.target.value })}/></Field><Field label="Tipo de interacción"><select value={values.kind} onChange={e => setValues({ ...values, kind: e.target.value })}><option value="">Todos los tipos</option>{kinds.map(k => <option key={k}>{k}</option>)}</select></Field><Field label="Desde"><input type="date" value={values.date_from} onChange={e => setValues({ ...values, date_from: e.target.value })}/></Field><Field label="Hasta"><input type="date" value={values.date_to} onChange={e => setValues({ ...values, date_to: e.target.value })}/></Field><div className="filter-actions"><button className="button primary" type="submit"><Search size={17}/>Aplicar</button><button className="button ghost" type="button" onClick={() => { setValues(emptyFilters); onApply(emptyFilters); setError(''); }}>Limpiar</button></div></form><Notice error>{error}</Notice></details>;
}

export function LocalNote() { return <div className="local-note"><ShieldCheck size={16} aria-hidden="true"/>Procesamiento local · Documentos originales conservados</div>; }
