import { useEffect, useRef, useState } from 'react';
import cytoscape, { type Core, type ElementDefinition } from 'cytoscape';
import { Maximize2, Minus, Plus, Scan, X } from 'lucide-react';
import { useData } from '../api';
import { useWorkspace } from '../context';
import { Empty, Loading, Notice } from './ui';
type GraphData = { nodes: ElementDefinition[]; edges: ElementDefinition[]; truncated: boolean; description: string };

function Canvas({ data }: { data: GraphData }) {
  const ref = useRef<HTMLDivElement>(null); const cy = useRef<Core | null>(null); const [selection, setSelection] = useState('');
  useEffect(() => {
    if (!ref.current) return;
    const graph = cytoscape({ container: ref.current, elements: [...data.nodes, ...data.edges], minZoom: .15, maxZoom: 5,
      layout: { name: 'circle', padding: 50, animate: false }, wheelSensitivity: .2,
      style: [
        { selector: 'node', style: { 'background-color': '#00b7cb', width: 26, height: 26, label: 'data(label)', color: '#f5f8fc', 'font-size': 11, 'text-valign': 'bottom', 'text-margin-y': 10, 'border-width': 5, 'border-color': '#0b4256', 'text-background-color': '#07182b', 'text-background-opacity': .9, 'text-background-padding': '3px' } },
        { selector: 'edge', style: { width: 1.5, 'line-color': '#426882', 'target-arrow-color': '#426882', 'target-arrow-shape': 'triangle', 'curve-style': 'bezier', opacity: .8 } },
        { selector: ':selected', style: { 'background-color': '#ffcb6b', 'line-color': '#ffcb6b', 'target-arrow-color': '#ffcb6b' } },
      ],
    }); cy.current = graph;
    graph.on('tap', 'node', e => setSelection(`Identificador observado: ${e.target.data('label')}`));
    graph.on('tap', 'edge', e => setSelection(`${e.target.data('weight')} interacciones registradas en este vínculo.`));
    const observer = new ResizeObserver(() => graph.resize()); observer.observe(ref.current);
    return () => { observer.disconnect(); graph.destroy(); cy.current = null; };
  }, [data]);
  const zoom = (factor: number) => { const graph = cy.current; if (graph) graph.zoom({ level: graph.zoom() * factor, renderedPosition: { x: graph.width() / 2, y: graph.height() / 2 } }); };
  return <><div className="graph-canvas" ref={ref} tabIndex={0} role="img" aria-label="Red de interacciones telefónicas. Usa los botones para acercar o ajustar, y la lista textual para consultar los vínculos." onKeyDown={e => { if (e.key === '+' || e.key === '=') { e.preventDefault(); zoom(1.2); } if (e.key === '-') { e.preventDefault(); zoom(.8); } if (e.key === 'Home') cy.current?.fit(undefined, 40); const moves: Record<string, { x: number; y: number }> = { ArrowLeft: { x: 30, y: 0 }, ArrowRight: { x: -30, y: 0 }, ArrowUp: { x: 0, y: 30 }, ArrowDown: { x: 0, y: -30 } }; if (moves[e.key]) { e.preventDefault(); cy.current?.panBy(moves[e.key]); } }}/><div className="visual-controls"><button className="icon-button" aria-label="Acercar red" onClick={() => zoom(1.3)}><Plus/></button><button className="icon-button" aria-label="Alejar red" onClick={() => zoom(.7)}><Minus/></button><button className="icon-button" aria-label="Ajustar red" onClick={() => cy.current?.fit(undefined, 40)}><Scan/></button></div><div className="graph-selection" aria-live="polite">{selection || 'Selecciona un nodo o vínculo para consultar su detalle.'}</div></>;
}

export default function Graph({ query }: { query: string }) {
  const { revision } = useWorkspace(); const { data, error, loading } = useData<GraphData>('/graph?' + query, revision);
  const dialog = useRef<HTMLDialogElement>(null); const [expanded, setExpanded] = useState(false);
  useEffect(() => { if (expanded) dialog.current?.showModal(); }, [expanded]);
  if (loading) return <Loading/>;
  if (error) return <Notice error>{error}</Notice>;
  if (!data?.nodes.length) return <Empty title="No hay vínculos representables">Se necesitan eventos con los números A y B informados.</Empty>;
  const labels = new Map(data.nodes.map(n => [n.data.id, n.data.label]));
  return <div className="graph-section"><div className="table-heading"><h2>Red de interacciones</h2><button className="button secondary" onClick={() => setExpanded(true)}><Maximize2 size={17}/>Pantalla completa</button></div><p className="visual-caption">{data.description} {data.truncated && 'Se muestran los 100 vínculos con más interacciones; usa filtros para acotar.'}</p><div className="graph-wrap"><Canvas data={data}/></div><details className="text-alternative"><summary>Consultar vínculos como lista accesible ({data.edges.length})</summary><ul>{data.edges.map(e => <li key={e.data.id}>{labels.get(e.data.source)} → {labels.get(e.data.target)}: {e.data.weight} interacciones</li>)}</ul></details>{expanded && <dialog ref={dialog} className="visual-dialog" aria-labelledby="full-graph-title" onClose={() => setExpanded(false)}><div className="section-heading"><h2 id="full-graph-title">Red de interacciones</h2><button className="icon-button" aria-label="Cerrar pantalla completa" onClick={() => { dialog.current?.close(); setExpanded(false); }}><X/></button></div><p className="visual-caption">Arrastra para mover. Usa + y − para acercar, o las flechas del teclado para desplazar.</p><div className="graph-wrap"><Canvas data={data}/></div></dialog>}</div>;
}
