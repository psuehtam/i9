'use client';
import {Database} from 'lucide-react';
import {ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, LineChart, Line, Legend} from 'recharts';
import {count, num, type Row} from '../lib/format';

function Empty({text = 'Nenhum registro para os filtros selecionados.'}: {text?: string}) {
  return (
    <div className="empty">
      <Database size={30} />
      <p>{text}</p>
    </div>
  );
}

function tooltipValue(value: any, integer: boolean) {
  return integer ? count(Number(value)) : num(Number(value), 2);
}

export function Chart({
  items,
  color = '#126753',
  dataKey = 'vehicles',
  unit = 'veículos',
  name,
}: {
  items: Row[];
  color?: string;
  dataKey?: string;
  unit?: string;
  name?: string;
}) {
  const total = items.length;
  const shown = items.slice(0, 10);
  const integer = dataKey === 'vehicles';
  const label = name || (dataKey === 'vehicles' ? 'Veículos' : 'MWh calculados');
  return items.length ? (
    <div className="chart">
      <ResponsiveContainer width="100%" height={265}>
        <BarChart data={shown} layout="vertical" margin={{left: 8, right: 24}}>
          <CartesianGrid strokeDasharray="3 3" horizontal={false} />
          <XAxis type="number" tickFormatter={(v) => count(v)} fontSize={12} label={{value: unit, position: 'insideBottomRight', offset: -2, fontSize: 11}} />
          <YAxis type="category" dataKey="name" width={128} fontSize={12} tickLine={false} axisLine={false} tick={{width: 120}} />
          <Tooltip formatter={(v: any) => [tooltipValue(v, integer), label]} labelFormatter={(label) => String(label)} />
          <Bar dataKey={dataKey} name={label} fill={color} radius={[0, 5, 5, 0]} barSize={19} />
        </BarChart>
      </ResponsiveContainer>
      <p className="caption">{total > 10 ? `Top 10 de ${total} grupos · eixo em ${unit}` : `Eixo em ${unit}`}</p>
    </div>
  ) : (
    <Empty />
  );
}

export function StackedCoverage({known, total}: {known: number; total: number}) {
  const unknown = Math.max(0, total - known);
  const pct = total ? (known / total) * 100 : 0;
  return (
    <div className="coverage-bar" aria-label={`Cobertura de bateria: ${count(known)} de ${count(total)}`}>
      <div className="coverage-track">
        <i style={{width: `${pct}%`}} />
      </div>
      <p className="caption">
        Com bateria identificada: {count(known)} · Sem identificação: {count(unknown)}
      </p>
    </div>
  );
}

export function SeriesChart({items}: {items: Row[]}) {
  if (!items.length) return <Empty text="Importe mais de um mês para ver a série." />;
  return (
    <div className="chart">
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={items} margin={{left: 8, right: 16, top: 8}}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="reference" fontSize={12} />
          <YAxis tickFormatter={(v) => count(v)} fontSize={12} />
          <Tooltip formatter={(v: any) => count(Number(v))} />
          <Legend />
          <Line type="monotone" dataKey="vehicles" name="Veículos no recorte" stroke="#126753" strokeWidth={2} dot />
          <Line type="monotone" dataKey="known_vehicles" name="Com bateria identificada" stroke="#3b6ea8" strokeWidth={2} dot />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function PropulsionChart({items, dataKey = 'vehicles', unit = 'veículos'}: {items: Row[]; dataKey?: string; unit?: string}) {
  if (!items.length) return <Empty />;
  const integer = dataKey === 'vehicles';
  return (
    <div className="chart">
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={items} margin={{left: 8, right: 16}}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="name" fontSize={12} />
          <YAxis tickFormatter={(v) => count(v)} fontSize={12} />
          <Tooltip formatter={(v: any) => [integer ? count(Number(v)) : num(Number(v), 2), unit]} />
          <Bar dataKey={dataKey} name={unit} fill="#126753" radius={[5, 5, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export {Empty};
