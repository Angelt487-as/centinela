import { useId, useRef, useState, type FormEvent } from 'react';
import { ArrowDownToLine, ArrowUpRight, BookOpen, Copy, ExternalLink, FileCheck2, Globe2, Link2, Plus, Search, ShieldCheck, Upload } from 'lucide-react';
import { api, download, jsonBody, upload, useData, useTask } from '../api';
import { useWorkspace } from '../context';
import type { Source } from '../types';
import { dateOnly, Empty, Field, Loading, Notice, number, PageHeading, Panel, TaskFeedback } from '../components/ui';
import PreparedSource, { SourceVerification } from '../components/PreparedSource';

function SourceCard({ source }: { source: Source }) {
  const input = useRef<HTMLInputElement>(null); const task = useTask(); const { refresh } = useWorkspace();
  const local = source.source_type === 'local_reference';
  const Icon = local ? BookOpen : Globe2;
  return <article className="source-card">
    <div className="source-card-heading"><span className="module-icon"><Icon size={22}/></span><div><h3>{source.title}</h3>{source.url ? <a href={source.url} target="_blank" rel="noopener noreferrer" className="source-url">{source.url}<ExternalLink size={14}/></a> : <span className="source-local-label">Material de referencia local · Sin URL pública</span>}</div><span className="badge neutral">{local ? 'Incorporado: ' : ''}{dateOnly(local ? source.created_at : source.observed_at)}</span></div>
    <p>{source.description || 'Sin descripción registrada.'}</p>
    <div className="source-meta"><span><FileCheck2 size={15}/>{source.evidence.length} {local ? 'documento(s) asociado(s)' : source.evidence.length === 1 ? 'evidencia' : 'evidencias'}</span>{local ? <SourceVerification source={source}/> : <span>{source.evidence.length ? 'SHA-256 calculado' : 'Sin evidencia adjunta'}</span>}</div>
    <details className="source-details"><summary>{local ? 'Consultar notas y documentos' : 'Consultar notas y evidencias'}</summary><div className="source-detail-content"><h4>Notas del registro</h4><p className="preserve-lines">{source.notes || 'No se añadieron notas.'}</p>{local && <><h4>Procedencia</h4><p className="preserve-lines">{source.provenance || 'No proporcionada'}</p></>}
      {source.evidence.map(e => <div className="evidence-item" key={e.id}><div className="section-heading"><strong>{e.name}</strong><button className="icon-button" aria-label={(local ? 'Descargar documento ' : 'Descargar evidencia ') + e.name} disabled={task.busy} onClick={() => void task.run(() => download('/files/' + e.id, e.name))}><ArrowDownToLine size={18}/></button></div><span className="muted">{number(e.size)} bytes · {dateOnly(e.created_at)}</span><div className="hash-block"><span>SHA-256</span><code>{e.sha256}</code><button className="text-button" onClick={() => void task.run(async () => { await navigator.clipboard.writeText(e.sha256); task.setMessage('Hash copiado al portapapeles.'); })}><Copy size={15}/>Copiar hash</button></div></div>)}
      {!source.is_demo && <><input className="sr-only" ref={input} type="file" aria-label={'Adjuntar evidencia a ' + source.title} accept=".pdf,.docx,.png,.jpg,.jpeg,.txt,.csv" onChange={e => { const file = e.target.files?.[0]; if (file) void task.run(async () => { await upload('/sources/' + source.id + '/evidence', file); refresh(); task.setMessage('Evidencia conservada. SHA-256 calculado.'); }); e.target.value = ''; }}/><button className="button secondary" disabled={task.busy} onClick={() => input.current?.click()}><Upload size={17}/>{local ? 'Adjuntar documento' : 'Adjuntar evidencia'}</button><p className="field-hint">PDF, Word, imagen, TXT o CSV. Máximo 25 MB.</p></>}
      <TaskFeedback task={task}/>
    </div></details>
  </article>;
}

export default function Sources() {
  const { revision, refresh } = useWorkspace(); const { data, loading, error } = useData<{ items: Source[] }>('/sources', revision); const task = useTask();
  const [search, setSearch] = useState(''); const [query, setQuery] = useState(''); const demoHeading = useId();
  const [form, setForm] = useState({ title: '', url: '', observed_at: new Date().toLocaleDateString('sv-SE'), description: '', notes: '' });
  async function submit(e: FormEvent) { e.preventDefault(); await task.run(async () => { await api('/sources', jsonBody(form)); setForm({ ...form, title: '', url: '', description: '', notes: '' }); refresh(); task.setMessage('Fuente registrada. Puedes adjuntar su evidencia en los detalles.'); }); }
  const items = data?.items.filter(s => [s.title, s.url || '', s.description, s.provenance || ''].join(' ').toLowerCase().includes(search.toLowerCase())) || [];
  const prepared = data?.items.filter(s => s.is_demo) || [];
  return <>
    <PageHeading number="02" title="Fuentes abiertas" description="Registra fuentes públicas y consulta material de referencia conservado." actions={<button className="button secondary" disabled={!data?.items.length || task.busy} onClick={() => void task.run(() => download('/sources/export', 'centinela-bitacora.csv'))}><ArrowDownToLine size={18}/>Exportar bitácora</button>}/>
    <Notice error>{error}</Notice>
    <section className="prepared-demo" aria-labelledby={demoHeading}><div className="section-heading"><div><h2 id={demoHeading}><BookOpen size={20} aria-hidden="true"/>Demostración preparada</h2><p>Registros persistentes obtenidos de los documentos originales disponibles.</p></div></div>{loading && !data ? <Loading label="Consultando la demostración preparada…"/> : prepared.length ? prepared.map(source => <PreparedSource source={source} key={source.id}/>) : !error && <Notice>No hay una demostración preparada en esta base. Ejecuta <code>scripts/cargar_demo_fuentes.py</code> antes de la presentación.</Notice>}</section>
    <div className="sources-layout"><Panel className="source-form-panel"><div className="section-heading"><div><h2><Plus size={20}/>Registrar una fuente</h2><p>Documenta lo que consultaste y cuándo.</p></div></div><form className="form-stack" onSubmit={submit}>
      <Field label="Título de la fuente *"><input required maxLength={200} value={form.title} placeholder="Un título que identifique la fuente" onChange={e => setForm({ ...form, title: e.target.value })}/></Field>
      <Field label="URL pública *" hint="Solo enlaces HTTP o HTTPS. No se accede automáticamente a la página."><input required type="url" maxLength={2000} value={form.url} placeholder="https://ejemplo.org/publicacion" onChange={e => setForm({ ...form, url: e.target.value })}/></Field>
      <Field label="Fecha de consulta *"><input type="date" required value={form.observed_at} onChange={e => setForm({ ...form, observed_at: e.target.value })}/></Field>
      <Field label="Descripción"><textarea rows={3} maxLength={4000} value={form.description} placeholder="¿Qué contiene esta fuente?" onChange={e => setForm({ ...form, description: e.target.value })}/></Field>
      <Field label="Notas"><textarea rows={3} maxLength={8000} value={form.notes} placeholder="Contexto de consulta y observaciones" onChange={e => setForm({ ...form, notes: e.target.value })}/></Field>
      <button className="button primary full" disabled={task.busy}><Plus size={18}/>Guardar fuente</button><TaskFeedback task={task}/>
    </form><div className="form-security-note"><ShieldCheck size={19}/><p>Adjunta el archivo conservado para calcular su SHA-256. El hash acredita la integridad del archivo, no la veracidad de su contenido.</p></div></Panel>
    <div className="source-results"><Panel className="external-search"><div><h2><Search size={19}/>Buscar en internet</h2><p>Búsqueda externa. Centinela no genera resultados actuales ni captura páginas automáticamente.</p></div><form onSubmit={e => { e.preventDefault(); if (query.trim()) window.open('https://www.google.com/search?q=' + encodeURIComponent(query), '_blank', 'noopener,noreferrer'); }}><Field label="Términos de búsqueda"><input type="search" value={query} onChange={e => setQuery(e.target.value)} placeholder="Escribe una consulta pública" required/></Field><button className="button secondary"><ArrowUpRight size={18}/>Abrir búsqueda externa</button></form></Panel>
      <div className="section-heading"><h2>Bitácora de fuentes <span className="badge neutral">{data?.items.length || 0}</span></h2></div><label className="search-field"><Search size={18}/><input aria-label="Filtrar fuentes registradas" type="search" placeholder="Filtrar por título, descripción o procedencia" value={search} onChange={e => setSearch(e.target.value)}/></label>{loading && !data ? <Loading/> : items.length ? items.map(s => <SourceCard source={s} key={s.id}/>) : <Panel><Empty title={search ? 'No hay coincidencias' : 'Tu bitácora está lista para comenzar'} icon={<Link2 size={30}/>}>{search ? 'Cambia los términos del filtro.' : 'Registra una fuente y adjunta la evidencia que conservaste.'}</Empty></Panel>}
    </div></div>
  </>;
}
