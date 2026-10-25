import { useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { GeoData, GeoEvent } from '../types';

export default function MapCanvas({ data, selected, tiles, lines, mode, onSelect }: { data: GeoData; selected: GeoEvent | null; tiles: boolean; lines: boolean; mode: 'eventos' | 'antenas'; onSelect: (event: GeoEvent) => void }) {
  const host = useRef<HTMLDivElement>(null); const map = useRef<L.Map | null>(null); const layer = useRef<L.LayerGroup | null>(null); const base = useRef<L.TileLayer | null>(null);
  useEffect(() => {
    if (!host.current) return;
    const instance = L.map(host.current, { center: [28.6, -106.1], zoom: 5, preferCanvas: false, zoomControl: false, attributionControl: false, zoomAnimation: false, fadeAnimation: false, markerZoomAnimation: false });
    L.control.zoom({ zoomInTitle: 'Acercar mapa', zoomOutTitle: 'Alejar mapa' }).addTo(instance);
    L.control.attribution({ prefix: false }).addTo(instance);
    map.current = instance; layer.current = L.layerGroup().addTo(instance);
    const observer = new ResizeObserver(() => instance.invalidateSize({ animate: false })); observer.observe(host.current);
    return () => { observer.disconnect(); instance.remove(); map.current = null; layer.current = null; base.current = null; };
  }, []);
  useEffect(() => {
    const instance = map.current; if (!instance || !layer.current) return;
    layer.current.clearLayers(); const markers: L.LatLngTuple[] = [];
    if (mode === 'eventos') {
      data.items.forEach(e => { if (e.latitude == null || e.longitude == null) return; const pos: L.LatLngTuple = [e.latitude, e.longitude]; markers.push(pos); const marker = L.circleMarker(pos, { radius: 5, color: '#67e8f9', weight: 1, fillColor: '#00b7cb', fillOpacity: .8 }).addTo(layer.current!); const text = document.createElement('span'); text.textContent = `${e.timestamp} · ${e.kind}`; marker.bindTooltip(text).on('click', () => onSelect(e)); });
    } else {
      data.antennas.forEach(a => { const pos: L.LatLngTuple = [a.latitude, a.longitude]; markers.push(pos); const node = L.circleMarker(pos, { radius: Math.min(18, 5 + Math.log2(a.connections + 1)), color: '#e6ccff', fillColor: '#b799ff', weight: 1, fillOpacity: .7 }).addTo(layer.current!); const text = document.createElement('span'); text.textContent = `${a.connections} conexiones · Azimut: ${a.azimuth ?? 'sin dato'}`; node.bindTooltip(text); });
    }
    if (lines) {
      const groups = new Map<string, L.LatLngTuple[]>();
      data.items.forEach(e => { if (e.subject && e.latitude != null && e.longitude != null) groups.set(e.subject, [...(groups.get(e.subject) || []), [e.latitude, e.longitude]]); });
      groups.forEach(points => { if (points.length > 1) L.polyline(points, { color: '#ffcb6b', weight: 2, dashArray: '6 8', opacity: .7, interactive: false }).addTo(layer.current!); });
    }
    if (markers.length) instance.fitBounds(L.latLngBounds(markers), { padding: [36, 36], maxZoom: 13, animate: false });
  }, [data, lines, mode, onSelect]);
  useEffect(() => {
    if (!map.current) return;
    if (tiles && !base.current) base.current = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a>', maxZoom: 19 }).addTo(map.current);
    if (!tiles && base.current) { map.current.removeLayer(base.current); base.current = null; }
  }, [tiles]);
  useEffect(() => { if (selected?.latitude != null && selected.longitude != null) map.current?.setView([selected.latitude, selected.longitude], Math.max(map.current.getZoom(), 12), { animate: false }); }, [selected]);
  return <div ref={host} className="leaflet-host" role="region" aria-label="Mapa interactivo de coordenadas. La secuencia de eventos proporciona una alternativa accesible mediante teclado."/>;
}
