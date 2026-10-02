'use client';
import {useEffect, useState} from 'react';
import {count} from './lib/format';

type Feature = {properties: {codarea: string}; geometry: {type: string; coordinates: any[]}};
const states: Record<string, string> = {
  '11': 'RO', '12': 'AC', '13': 'AM', '14': 'RR', '15': 'PA', '16': 'AP', '17': 'TO', '21': 'MA', '22': 'PI', '23': 'CE', '24': 'RN', '25': 'PB', '26': 'PE', '27': 'AL', '28': 'SE', '29': 'BA', '31': 'MG', '32': 'ES', '33': 'RJ', '35': 'SP', '41': 'PR', '42': 'SC', '43': 'RS', '50': 'MS', '51': 'MT', '52': 'GO', '53': 'DF',
};
const point = ([lon, lat]: number[]) => [(lon + 74) * 11, (6 - lat) * 11];
function polygon(rings: number[][][]) {
  return rings.map((r) => 'M' + r.map((p) => point(p).join(',')).join('L') + 'Z').join('');
}

export default function UFMap({
  items,
  selected,
  onSelect,
  metric = 'vehicles',
}: {
  items: {name: string; vehicles: number; vehicles_per_100k?: number | null; population?: number | null}[];
  selected?: string;
  onSelect: (uf: string) => void;
  metric?: 'vehicles' | 'per_capita';
}) {
  const [features, setFeatures] = useState<Feature[]>([]);
  const [failed, setFailed] = useState(false);
  const [hover, setHover] = useState<{uf: string; value: number | null; x: number; y: number} | null>(null);
  useEffect(() => {
    const c = new AbortController();
    fetch('/br-uf.geojson', {signal: c.signal})
      .then((r) => {
        if (!r.ok) throw Error();
        return r.json();
      })
      .then((r: any) => setFeatures(r.features))
      .catch((e) => {
        if (e.name !== 'AbortError') setFailed(true);
      });
    return () => c.abort();
  }, []);
  const values = Object.fromEntries(items.map((r) => [r.name, metric === 'per_capita' ? r.vehicles_per_100k || 0 : r.vehicles]));
  const max = Math.max(1, ...Object.values(values).map(Number));
  const stops = [0, 0.25, 0.5, 0.75, 1].map((p) => Math.round(max * p));
  if (failed) return <p className="caption">Mapa indisponível. Consulte a distribuição por UF abaixo.</p>;
  return (
    <div className="uf-map">
      <svg viewBox="0 0 465 450" role="group" aria-label="Mapa do Brasil por UF. Selecione um estado para filtrar.">
        {features.map((f) => {
          const uf = states[f.properties.codarea];
          const qty = values[uf];
          const ratio = (qty || 0) / max;
          const label = metric === 'per_capita' ? `${count(qty)} / 100 mil hab.` : `${count(qty)} veículos`;
          return (
            <path
              key={uf}
              d={f.geometry.type === 'Polygon' ? polygon(f.geometry.coordinates) : f.geometry.coordinates.map(polygon).join('')}
              fill={qty ? `hsl(159, ${30 + ratio * 25}%, ${80 - ratio * 52}%)` : '#edf2f1'}
              stroke={selected === uf ? '#122e28' : '#fff'}
              strokeWidth={selected === uf ? 2.5 : 1.3}
              role="button"
              tabIndex={0}
              aria-label={`${uf}: ${qty === undefined ? 'sem registros no recorte' : label}`}
              onClick={() => onSelect(selected === uf ? '' : uf)}
              onMouseMove={(e) => setHover({uf, value: qty ?? null, x: e.clientX, y: e.clientY})}
              onMouseLeave={() => setHover(null)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  onSelect(selected === uf ? '' : uf);
                }
              }}
            />
          );
        })}
      </svg>
      {hover && (
        <div className="map-tooltip" style={{left: hover.x + 12, top: hover.y + 12}} role="status">
          <strong>{hover.uf}</strong>
          <span>{hover.value == null ? 'Sem registros no recorte' : metric === 'per_capita' ? `${count(hover.value)} por 100 mil habitantes` : `${count(hover.value)} veículos`}</span>
        </div>
      )}
      <div className="map-legend">
        <span>{count(stops[0])}</span>
        <i />
        <span>{count(stops[2])}</span>
        <i />
        <span>{count(stops[4])}</span>
      </div>
      <p className="caption">
        Geometria: IBGE · cinza = sem registros no recorte · clique para filtrar · {metric === 'per_capita' ? 'por 100 mil habitantes' : 'quantidade absoluta'}
      </p>
    </div>
  );
}
