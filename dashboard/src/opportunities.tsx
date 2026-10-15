import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useResource, type Page } from './api';
import { Badge, Empty, ErrorState, Heading, Loading, Note, Pager, number, vehicleType, electrification } from './ui';

interface Opportunity { id: string; public_code?: string; manufacturer?: string; model?: string; registry_manufacturer?: string; registry_model?: string; registry_category?: string; registry_powertrain?: string; vehicle_category?: string; powertrain_type?: string; battery_id?: string; state?: string; municipality?: string; location_simulated?: boolean; soh_percent?: number; threshold_pct: number; distance_pct?: number; trend_pct?: number; observed_at?: string; reason: string; status: string; }
interface Response extends Page<Opportunity> { mode: 'real' | 'simulated'; soh_limit: number; }
interface Passport { vehicle_id: string; battery_id: string; chemistry: string; capacity_kwh: number; soh_percent: number; source: string; passport: { fields: { id: string; label: string; group: string }[]; values: Record<string, { value: string | null; status: string; reason?: string }> }; }
interface Region { state?: string; municipality?: string; manufacturer?: string; model?: string; vehicle_category?: string; powertrain_type?: string; vehicles: number; older_vehicles: number; }
interface RegionResponse extends Page<Region> { reference?: string; note?: string; }
const labels: Record<string, string> = { priority: 'Avaliação prioritária', near: 'Próximo do limite', monitor: 'Acompanhar', stale: 'Medição antiga', insufficient: 'Dados insuficientes' };
export function OpportunitiesPage() {
  const [reference, setReference] = useState(''); const [state, setState] = useState(''); const [municipality, setMunicipality] = useState('');
  const [category, setCategory] = useState(''); const [powertrain, setPowertrain] = useState(''); const [model, setModel] = useState(''); const [offset, setOffset] = useState(0);
  const query = new URLSearchParams({ limit: '50', offset: String(offset) });
  for (const [key, value] of Object.entries({ reference, state, municipality, vehicle_category: category, powertrain_type: powertrain, model })) if (value) query.set(key, value);
  const result = useResource<Response>('/opportunities?' + query.toString());
  const regions = useResource<RegionResponse>('/opportunities/regions?' + query.toString());
  const mode = result.data?.mode;
  return <><Heading eyebrow="BATERIAS" title="Oportunidades" description="Veículos priorizados pela saúde da bateria e pela origem das medições." />
    {mode && <Note warning={mode === 'simulated'}>{mode === 'simulated' ? 'SIMULAÇÃO: todos os dados de bateria e oportunidades nesta tela são fictícios.' : 'Dados reais: apenas veículos identificados com bateria vinculada aparecem como candidatos individuais.'}</Note>}
    <section className="panel"><div className="section-heading"><h2>Filtrar candidatos</h2></div><div className="filter-panel">
      <label className="field"><span>Mês</span><input type="month" value={reference} onChange={e => { setReference(e.target.value); setOffset(0); }} /></label>
      <label className="field"><span>UF</span><input maxLength={2} value={state} onChange={e => { setState(e.target.value.toUpperCase()); setOffset(0); }} /></label>
      <label className="field"><span>Município</span><input value={municipality} onChange={e => { setMunicipality(e.target.value); setOffset(0); }} /></label>
      <label className="field"><span>Categoria</span><select value={category} onChange={e => { setCategory(e.target.value); setOffset(0); }}><option value="">Todas</option>{['car','bus','microbus','truck','tractor_truck','van','utility','motorcycle'].map(x => <option key={x} value={x}>{vehicleType(x)}</option>)}</select></label>
      <label className="field"><span>Motorização</span><select value={powertrain} onChange={e => { setPowertrain(e.target.value); setOffset(0); }}><option value="">Todas</option>{['BEV','PHEV','HEV','HEV_FLEX','MHEV_12V','MHEV_48V'].map(x => <option key={x} value={x}>{electrification(x)}</option>)}</select></label>
      <label className="field"><span>Modelo</span><input value={model} onChange={e => { setModel(e.target.value); setOffset(0); }} /></label>
    </div></section>
    {result.error ? <ErrorState error={result.error} retry={result.reload} /> : !result.data ? <Loading /> : <section className="panel"><div className="section-heading"><h2>Veículos priorizados</h2><small>Limite de saúde: {result.data.soh_limit}%</small></div>
      {result.data.items.map(item => <div className="history-row" key={item.id + item.battery_id}><div><strong>{item.registry_manufacturer || item.manufacturer} {item.registry_model || item.model}</strong><small>{item.public_code || item.id} · {vehicleType(item.registry_category || item.vehicle_category)} · {electrification(item.registry_powertrain || item.powertrain_type || '')}</small><small>{item.state || 'UF desconhecida'} / {item.municipality || 'Município desconhecido'}{item.location_simulated ? ' · local simulado' : ''}</small><small>{item.soh_percent == null ? 'Saúde não medida' : `Saúde: ${item.soh_percent}%`} · {item.reason}</small></div><Badge tone={item.status === 'priority' ? 'red' : item.status === 'near' ? 'amber' : ''}>{labels[item.status] || item.status}</Badge>{mode === 'simulated' ? <Link className="button secondary" to={'/oportunidades/simulacao/' + item.id}>Ver bateria fictícia</Link> : <Link className="button secondary" to={'/baterias/' + item.battery_id}>Ver bateria</Link>}</div>)}
      {!result.data.items.length && <Empty title="Nenhuma oportunidade encontrada">Ajuste os filtros ou aguarde a chegada de dados individuais de baterias.</Empty>}
      <Pager total={result.data.total} offset={offset} setOffset={setOffset} /></section>}
    <section className="panel"><div className="section-heading"><h2>Estimativas por região e modelo</h2></div><Note>Contagem de veículos com oito anos ou mais. Esses números não identificam uma bateria nem medem sua saúde.</Note>
      {regions.error ? <ErrorState error={regions.error} retry={regions.reload} /> : !regions.data ? <Loading /> : regions.data.items.map((item, index) => <div className="history-row" key={index}><div><strong>{item.state || 'UF desconhecida'} / {item.municipality || 'Município desconhecido'}</strong><small>{item.manufacturer} {item.model} · {electrification(item.powertrain_type || '')} · {vehicleType(item.vehicle_category)}</small><small>{number(item.older_vehicles)} veículos com oito anos ou mais entre {number(item.vehicles)} do grupo</small></div></div>)}
    </section>
  </>;
}
export function SimulatedPassportPage() {
  const { id } = useParams(); const result = useResource<Passport>(id ? '/opportunities/simulated/' + id + '/passport' : null);
  if (result.error) return <ErrorState error={result.error} retry={result.reload} />;
  if (!result.data) return <Loading />;
  const p = result.data;
  return <><Heading eyebrow="SIMULAÇÃO" title="Bateria fictícia" description="Dados criados para demonstrar o dashboard. Não representam uma bateria física." />
    <Note warning>{p.source}</Note><section className="panel"><h2>Resumo</h2><p>Veículo: <Link to={'/veiculos/unidades/' + p.vehicle_id}>{p.vehicle_id}</Link></p><p>Bateria simulada: {p.battery_id}</p><p>Capacidade: {number(p.capacity_kwh)} kWh · Química: {p.chemistry} · Saúde: {p.soh_percent}%</p></section>
    <section className="panel"><h2>Passaporte simulado · 71 campos</h2>{p.passport.fields.map(field => { const value = p.passport.values[field.id]; return <div className="history-row" key={field.id}><div><strong>{field.id}. {field.label}</strong><small>{field.group}</small><p>{value?.status === 'not_applicable' ? `Não aplicável: ${value.reason}` : value?.value}</p></div></div>; })}</section></>;
}
