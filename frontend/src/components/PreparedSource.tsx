import { useEffect, useId, useRef, useState } from 'react';
import { ArrowDownToLine, BookOpen, FileText, Info, ShieldCheck, X } from 'lucide-react';
import { download, useData, useTask } from '../api';
import type { Source } from '../types';
import { dateTime, Loading, Notice } from './ui';

type DocumentView = { source_id: string; file_id: string; name: string; document_type: string; text: string; sha256: string; notice: string };
type IntegrityView = { source_id: string; file_id: string; name: string; stored_sha256: string; computed_sha256: string; matches: boolean; archive_matches: boolean | null; checked_at: string; notice: string };
type View = 'details' | 'document' | 'integrity';
const titles: Record<View, string> = { details: 'Detalles del registro', document: 'Documento de referencia', integrity: 'Integridad SHA-256' };

export function SourceVerification({ source }: { source: Source }) {
  return <span className={`badge ${source.verification_status === 'integridad_comprobada' ? '' : 'neutral'}`}><ShieldCheck size={13} aria-hidden="true"/>{source.verification_status === 'integridad_comprobada' ? 'Integridad comprobada al incorporar' : 'Pendiente de verificación'}</span>;
}

export default function PreparedSource({ source }: { source: Source }) {
  const [view, setView] = useState<View | null>(null);
  const dialog = useRef<HTMLDialogElement>(null); const titleId = useId(); const task = useTask();
  const details = useData<Source>(view === 'details' ? '/sources/' + source.id : null);
  const document = useData<DocumentView>(view === 'document' ? `/sources/${source.id}/document` : null);
  const integrity = useData<IntegrityView>(view === 'integrity' ? `/sources/${source.id}/integrity` : null);
  useEffect(() => { if (view && !dialog.current?.open) dialog.current?.showModal(); }, [view]);
  const busy = details.loading || document.loading || integrity.loading;
  const error = details.error || document.error || integrity.error || task.error;
  const record = details.data;
  const file = source.evidence[0];
  return <article className="demo-source-card">
    <div className="demo-source-heading"><span className="module-icon"><BookOpen size={25} aria-hidden="true"/></span><div><span className="eyebrow">MATERIAL DE REFERENCIA DEL HACKATHON</span><h3>{source.title}</h3></div><SourceVerification source={source}/></div>
    <p className="demo-source-description">{source.description}</p>
    <dl className="demo-source-meta"><div><dt>Tipo de fuente</dt><dd>Documento local de referencia · {source.document_type || 'Tipo no informado'}</dd></div><div><dt>Documento asociado</dt><dd>{file?.name || 'Documento no asociado'}</dd></div><div><dt>Fecha de incorporación</dt><dd>{dateTime(source.created_at)}</dd></div></dl>
    <p className="reference-scope"><Info size={16} aria-hidden="true"/>Material local conservado del hackathon. No es evidencia obtenida de internet ni un resultado de búsqueda pública.</p>
    <div className="demo-source-actions"><button className="button primary" onClick={() => setView('details')}><Info size={17}/>Ver detalles</button><button className="button secondary" onClick={() => setView('document')} disabled={!file}><FileText size={17}/>Ver documento</button><button className="button secondary" onClick={() => setView('integrity')} disabled={!file}><ShieldCheck size={17}/>Ver integridad SHA-256</button></div>
    {view && <dialog ref={dialog} className="reference-dialog" aria-labelledby={titleId} onClose={() => setView(null)}><div className="section-heading"><div><h2 id={titleId}>{titles[view]}</h2><p className="break-word">{source.title}</p></div><button className="icon-button" aria-label="Cerrar vista de referencia" onClick={() => dialog.current?.close()}><X/></button></div><Notice error>{error}</Notice>{busy && <Loading label="Consultando el registro conservado…"/>}
      {view === 'details' && record && <><SourceVerification source={record}/><dl className="reference-record"><div><dt>Título</dt><dd>{record.title}</dd></div><div><dt>Tipo de fuente</dt><dd>{record.source_type === 'local_reference' ? 'Material de referencia del hackathon' : 'Fuente web'}</dd></div><div><dt>Tipo de documento</dt><dd>{record.document_type || 'No informado'}</dd></div><div><dt>Descripción</dt><dd>{record.description || 'No proporcionada'}</dd></div><div><dt>Procedencia</dt><dd>{record.provenance || 'No proporcionada'}</dd></div><div><dt>Fecha de incorporación</dt><dd>{dateTime(record.created_at)}</dd></div><div><dt>Fecha de consulta web</dt><dd>{record.observed_at ? dateTime(record.observed_at) : 'No aplica: documento local'}</dd></div><div><dt>URL pública</dt><dd>{record.url ? <a className="text-link" href={record.url} target="_blank" rel="noopener noreferrer">{record.url}</a> : 'Sin URL pública'}</dd></div><div><dt>Archivo original</dt><dd>{record.evidence[0]?.name || 'No asociado'}</dd></div><div><dt>Observaciones</dt><dd className="preserve-lines">{record.notes || 'Sin observaciones adicionales'}</dd></div></dl><Notice>La verificación indicada se refiere a la integridad del archivo. No verifica la vigencia, veracidad o validez jurídica de su contenido.</Notice><div className="demo-source-actions"><button className="button secondary" disabled={task.busy} onClick={() => void task.run(() => download(`/sources/${source.id}/export`, 'centinela-registro-referencia.csv'))}><ArrowDownToLine size={17}/>Exportar registro</button><button className="button secondary" onClick={() => setView('document')}><FileText size={17}/>Ver documento</button></div></>}
      {view === 'document' && document.data && <><Notice>{document.data.notice}</Notice><div className="reference-file-heading"><FileText size={21} aria-hidden="true"/><strong>{document.data.name}</strong><span className="badge neutral">{document.data.document_type}</span></div><pre className="reference-document-text" tabIndex={0} aria-label="Texto extraído del documento original">{document.data.text}</pre><button className="button primary" disabled={task.busy} onClick={() => void task.run(() => download('/files/' + document.data!.file_id, document.data!.name))}><ArrowDownToLine size={17}/>Descargar original</button></>}
      {view === 'integrity' && integrity.data && <><Notice error={!integrity.data.matches || integrity.data.archive_matches === false} success={integrity.data.matches && integrity.data.archive_matches === true}>{!integrity.data.matches ? 'Los hashes no coinciden. La integridad del archivo conservado no pudo confirmarse.' : integrity.data.archive_matches === false ? 'Los hashes del archivo conservado coinciden, pero el documento actual del ZIP es diferente.' : 'Hash conservado y hash recalculado coinciden.'}</Notice>{integrity.data.archive_matches === false && <Notice error>El documento disponible en el ZIP original no coincide con el archivo conservado. Revisa su procedencia antes de utilizarlo.</Notice>}<dl className="reference-record"><div><dt>Archivo comprobado</dt><dd>{integrity.data.name}</dd></div><div><dt>Comprobación realizada</dt><dd>{dateTime(integrity.data.checked_at)}</dd></div><div><dt>Comparación con el ZIP original</dt><dd>{integrity.data.archive_matches === null ? 'No disponible para esta comprobación' : integrity.data.archive_matches ? 'Los bytes coinciden con el documento del ZIP original' : 'No coincide con el documento disponible en el ZIP original'}</dd></div></dl><div className="hash-block"><strong>SHA-256 conservado al incorporar</strong><code>{integrity.data.stored_sha256}</code></div><div className="hash-block"><strong>SHA-256 recalculado del archivo conservado</strong><code>{integrity.data.computed_sha256}</code></div><Notice>{integrity.data.notice}</Notice></>}
    </dialog>}
  </article>;
}
