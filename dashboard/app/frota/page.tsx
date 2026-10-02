'use client';
import {useEffect, useState} from 'react';
import UFMap from '../uf-map';
import {BatteryCharging, CarFront, Download, RefreshCw, ShieldCheck, SlidersHorizontal, X, Activity, MapPin, CalendarDays, Zap, ArrowUpRight, ExternalLink} from 'lucide-react';
import {Tabs, TabsList, TabsTrigger, TabsContent} from '@/components/ui/tabs';
import {Table, TableBody, TableCell, TableHead, TableHeader, TableRow} from '@/components/ui/table';
import {Button} from '@/components/ui/button';
import {Progress} from '@/components/ui/progress';
import {ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip} from 'recharts';
import {Chart, Empty, SeriesChart, StackedCoverage, PropulsionChart} from '../components/charts';
import {Picker} from '../components/picker';
import {apiGet, count, dt, month, num, PALETTE, PROPULSION, type Row} from '../lib/format';
import OperationalHeader from '../components/operational-header';

const API = '/api/v1';
const labels: Row = {
  reference: 'Referência mensal', uf: 'Estado', city: 'Município', brand: 'Marca', model: 'Modelo', version: 'Versão',
  vehicle_year: 'Ano do veículo', chemistry: 'Química', confidence: 'Correspondência', source: 'Fonte',
  capacity_min: 'Capacidade mín. (kWh)', capacity_max: 'Capacidade máx. (kWh)', warranty_end: 'Fim da garantia (ano)',
  target_year: 'Janela estimada (ano)', propulsion: 'Propulsão',
};

function Export({report, query}: {report: string; query: string}) {
  return (
    <div className="export">
      <a href={`${API}/export/${report}?${query}&format=csv`}><Download size={14}/> CSV</a>
      <a href={`${API}/export/${report}?${query}&format=xlsx`}>Excel</a>
    </div>
  );
}
function DataTable({heads, children}: {heads: string[]; children: React.ReactNode}) {
  return <Table><TableHeader><TableRow>{heads.map((h) => <TableHead key={h}>{h}</TableHead>)}</TableRow></TableHeader><TableBody>{children}</TableBody></Table>;
}

export default function Dashboard({embedded=false,initialTab='overview',externalKey=''}: {embedded?:boolean;initialTab?:string;externalKey?:string} = {}) {
  const [f, setF] = useState<Record<string, string>>({});
  const [options, setOptions] = useState<Row>({});
  const [scenario, setScenario] = useState('8');
  const [tab, setTab] = useState(initialTab);
  const [advanced, setAdvanced] = useState(false);
  const [data, setData] = useState<Row | null>(null);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [revision, setRevision] = useState(0);
  const [key, setKey] = useState(externalKey);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [history, setHistory] = useState(false);
  const [mapMetric, setMapMetric] = useState<'vehicles' | 'per_capita'>('vehicles');
  const query = new URLSearchParams({...Object.fromEntries(Object.entries(f).filter(([, v]) => v)), scenario}).toString();
  function change(k: string, v: string) {
    setPage(0);
    setF((p) => {
      const n = {...p, [k]: v};
      if (k === 'uf') delete n.city;
      if (k === 'brand') { delete n.model; delete n.version; }
      if (k === 'model') delete n.version;
      return n;
    });
  }
  useEffect(() => {
    const c = new AbortController();
    const q = new URLSearchParams(Object.fromEntries(Object.entries(f).filter(([k, v]) => ['reference', 'uf', 'brand', 'model'].includes(k) && v)));
    apiGet(API + '/filters?' + q, c.signal).then((o) => {
      setOptions(o);
      if (!f.reference && o.references.length) setF((p) => ({...p, reference: o.references[0]}));
    }).catch((e) => { if (e.name !== 'AbortError') setError(e.message); });
    return () => c.abort();
  }, [f.reference, f.uf, f.brand, f.model, revision]);
  useEffect(() => {
    const c = new AbortController();
    setLoading(true); setError('');
    Promise.all([
      apiGet(API + '/summary?' + query, c.signal),
      apiGet(API + '/fleet?' + query + `&limit=25&offset=${page * 25}`, c.signal),
      apiGet(API + '/forecast?' + query, c.signal),
      apiGet(API + '/monthly-change?' + query, c.signal),
      apiGet(API + '/monthly-series?' + query, c.signal),
      apiGet(API + '/data-quality?' + query, c.signal),
      apiGet(API + '/sources', c.signal),
      apiGet(API + '/batteries', c.signal),
    ]).then(([summary, fleet, forecast, monthly, series, quality, sources, batteries]) => setData({summary, fleet, forecast, monthly, series, quality, sources, batteries}))
      .catch((e) => { if (e.name !== 'AbortError') setError(e.message); })
      .finally(() => { if (!c.signal.aborted) setLoading(false); });
    return () => c.abort();
  }, [query, page, revision]);
  const running = data?.quality.runs.some((r: Row) => r.status === 'EXECUTANDO');
  useEffect(() => {
    if (!running) return;
    const id = setInterval(() => setRevision((x) => x + 1), 10000);
    return () => clearInterval(id);
  }, [running]);
  async function admin(action: string) {
    setBusy(true); setMessage('');
    try {
      const r = await fetch(API + '/admin/' + action, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-Admin-Key': key}, body: action === 'etl/run' ? '{}' : undefined});
      const result: any = await r.json();
      if (!r.ok) throw Error(result.detail || 'Operação falhou');
      setMessage(action === 'technical/download' ? `${count(result.br_records)} registros técnicos BR salvos; ${count(result.inserted)} novos. Aguardam revisão antes do cálculo de energia.` : action === 'etl/run' ? 'Atualização iniciada. Acompanhe as etapas abaixo.' : 'Testes de conexão concluídos.');
      setRevision((x) => x + 1);
    } catch (e: any) { setMessage(e.message); } finally { setBusy(false); }
  }
  const s = data?.summary;
  const activeChecks = (data?.quality.api_checks || []).filter((r: Row, i: number, all: Row[]) => ['SENATRAN catálogo', 'IBGE municípios', 'OpenEV GitHub'].includes(r.name) && all.findIndex((x) => x.name === r.name) === i);
  const shownChecks = history ? (data?.quality.api_checks || []) : activeChecks;
  const shownRuns = history ? (data?.quality.runs || []) : (data?.quality.runs || []).slice(0, 1);
  const propulsionItems = (s?.by_propulsion || []).map((r: Row) => ({...r, name: PROPULSION[r.name] || r.name}));
  return (
    <div className={embedded ? 'embedded-reports' : ''}>
      {!embedded&&<OperationalHeader active="reports"/>}
      <main>
        <div className="page-heading">
          <div>
            <div className="eyebrow">INTELIGÊNCIA DE DADOS</div>
            <h1>Frota eletrificada, em perspectiva.</h1>
            <p>Todos os veículos com bateria de tração — elétricos, híbridos e plug-in — e as janelas futuras desses packs.</p>
          </div>
          <div className="reference"><CalendarDays size={18}/><div><small>REFERÊNCIA SELECIONADA</small><strong>{month(f.reference || s?.reference)}</strong></div></div>
        </div>
        <section className="filters-panel" aria-label="Filtros">
          <div className="filter-grid">
            {['reference', 'uf', 'city', 'brand', 'model', 'vehicle_year'].map((k) => (
              <Picker key={k} label={labels[k]} value={f[k] || ''} options={(options[k === 'reference' ? 'references' : k] || []).map(String)} onChange={(v) => change(k, v)} />
            ))}
          </div>
          <div className="filter-footer">
            <Button variant="ghost" onClick={() => setAdvanced(!advanced)} aria-expanded={advanced}><SlidersHorizontal size={15}/>{advanced ? 'Menos filtros' : 'Mais filtros'}</Button>
            <button className="text-button" onClick={() => { setF(f.reference ? {reference: f.reference} : {}); setPage(0); }}><X size={14}/> Limpar filtros</button>
            <span>Filtros aplicados a todos os relatórios</span>
          </div>
          {advanced && (
            <div className="filter-grid advanced">
              <Picker label={labels.propulsion} value={f.propulsion || ''} options={(options.propulsion || []).map(String)} onChange={(v) => change('propulsion', v)} format={(v) => PROPULSION[v] || v} />
              {['version', 'chemistry', 'confidence', 'source'].map((k) => (
                <Picker key={k} label={labels[k]} value={f[k] || ''} options={(options[k === 'source' ? 'source_id' : k] || []).map(String)} onChange={(v) => change(k, v)} />
              ))}
              {['capacity_min', 'capacity_max', 'warranty_end', 'target_year'].map((k) => (
                <label className="filter" key={k}><span>{labels[k]}</span><input type="number" min={k.includes('capacity') ? 0 : 1990} max={k.includes('capacity') ? 500 : 2100} value={f[k] || ''} onChange={(e) => change(k, e.target.value)} placeholder="Todos"/></label>
              ))}
            </div>
          )}
        </section>
        {error && <div role="alert" className="error">{error}<Button variant="outline" onClick={() => setRevision((x) => x + 1)}>Tentar novamente</Button></div>}
        {loading && <div role="status" className="loading"><RefreshCw size={14}/> Consultando dados…</div>}
        {!error && data && (
          <div className={loading ? 'refreshing' : ''} aria-busy={loading}>
            <div className="scope-note"><ShieldCheck size={18}/>{s.scope}</div>
            <div className="kpi-grid">
              <article className="kpi"><div>Veículos no recorte <CarFront size={19}/></div><strong>{count(s.vehicles)}</strong><span>{s.official_ruler_pct != null ? `${num(s.official_ruler_pct, 1)}% da régua SENATRAN por combustível (${count(s.official_ruler_total)})` : (data.monthly.available ? `${data.monthly.delta >= 0 ? '+' : ''}${count(data.monthly.delta)} em relação ao mês anterior` : 'Famílias validadas · não é o acumulado ABVE')}</span></article>
              <article className="kpi energy"><div>Energia identificada <Zap size={19}/></div><strong>{num(s.energy_mwh, 1)} <small>MWh</small></strong><span>Só fichas aceitas · BEV/PHEV/HEV separados abaixo</span></article>
              <article className="kpi"><div>Modelos identificados <BatteryCharging size={19}/></div><strong>{count(s.models)}</strong><span>{count(s.brands)} marcas · {count(s.versions)} versões</span></article>
              <article className="kpi"><div>Cobertura de bateria <ShieldCheck size={19}/></div><strong>{num(s.coverage_pct, 1)}<small>%</small></strong><Progress value={s.coverage_pct} aria-label="Cobertura de bateria"/><StackedCoverage known={s.known_vehicles} total={s.vehicles}/></article>
            </div>
            <Tabs className="report-tabs" value={tab} onValueChange={(v) => setTab(String(v))}>
              <TabsList className="main-tabs" variant="line">{[['overview', 'Visão geral'], ['fleet', 'Frota detalhada'], ['batteries', 'Baterias'], ['forecast', 'Janelas futuras'], ['monthly', 'Evolução mensal'], ['quality', 'Fontes e qualidade']].filter(([k])=>!embedded||(initialTab==='quality'?k==='quality':['overview','forecast','monthly'].includes(k))).map(([k, v]) => <TabsTrigger key={k} value={k}>{v}</TabsTrigger>)}</TabsList>
              <TabsContent value="overview">
                <div className="overview-grid">
                  <section className="panel distribution-panel">
                    <div className="panel-heading"><div><span className="eyebrow">DISTRIBUIÇÃO</span><h2>Onde está a frota?</h2></div><MapPin/></div>
                    <div className="scenario-buttons">
                      <Button variant={mapMetric === 'vehicles' ? 'default' : 'outline'} onClick={() => setMapMetric('vehicles')}>Quantidade</Button>
                      <Button variant={mapMetric === 'per_capita' ? 'default' : 'outline'} onClick={() => setMapMetric('per_capita')}>Por 100 mil hab.</Button>
                    </div>
                    <UFMap items={s.by_uf} selected={f.uf} onSelect={(v) => change('uf', v)} metric={mapMetric}/>
                    <Chart items={s.by_uf} color={PALETTE.uf}/>
                    <p className="caption">Veículos por UF · recorte selecionado</p>
                  </section>
                  <section className="panel"><div className="panel-heading"><div><span className="eyebrow">PROPULSÃO</span><h2>Elétricos e híbridos</h2></div><CarFront/></div><PropulsionChart items={propulsionItems}/><p className="caption">Estoque do recorte por família. Meta de cobertura: SENATRAN por combustível, não o KPI ABVE.</p></section>
                  <section className="panel"><div className="panel-heading"><div><span className="eyebrow">PARTICIPAÇÃO</span><h2>Marcas em circulação</h2></div><CarFront/></div><Chart items={s.by_brand} color={PALETTE.brand}/><p className="caption">Quantidade de veículos por marca</p></section>
                  <section className="panel"><h2>Municípios com mais veículos</h2><Chart items={s.by_city} color={PALETTE.city}/><p className="caption">Veículos por município · recorte selecionado</p></section>
                  <section className="panel insight">
                    <BatteryCharging size={32}/>
                    <span className="eyebrow">COMO LER ESTES DADOS</span>
                    <h2>Garantia não é vida útil.</h2>
                    <p>Os cenários somam 8, 10 ou 12 anos ao ano do veículo. São janelas de planejamento, não datas certas de falha ou descarte.</p>
                    <p>A energia inclui apenas baterias com correspondência aceita, separada por BEV, PHEV e HEV. Ampliar o catálogo não altera junho/julho já publicados: rode um mês novo de ETL. A régua oficial por combustível está no KPI e na aba de qualidade — não use o acumulado ABVE como meta.</p>
                    <Button onClick={() => setTab('forecast')}>Explorar janelas futuras <ArrowUpRight size={16}/></Button>
                  </section>
                </div>
              </TabsContent>
              <TabsContent value="fleet">
                <section className="panel">
                  <div className="panel-heading"><div><h2>Frota por modelo e município</h2><p>{count(data.fleet.total)} grupos de veículos · dados agregados, sem placas</p></div><Export report="fleet" query={query}/></div>
                  {data.fleet.items.length ? (
                    <>
                      <DataTable heads={['Marca / modelo', 'Versão', 'Propulsão', 'Município / UF', 'Ano', 'Veículos', 'Bateria', 'Correspondência']}>
                        {data.fleet.items.map((r: Row) => (
                          <TableRow key={r.id}>
                            <TableCell><strong>{r.brand}</strong><span className="subcell">{r.model}</span></TableCell>
                            <TableCell>{r.version}</TableCell>
                            <TableCell>{PROPULSION[r.propulsion] || r.propulsion || '—'}</TableCell>
                            <TableCell>{r.city}<span className="subcell">{r.uf}</span></TableCell>
                            <TableCell>{r.vehicle_year ?? 'Não informado'}</TableCell>
                            <TableCell>{count(r.quantity)}</TableCell>
                            <TableCell>{r.capacity_kwh ? `${num(r.capacity_kwh, 1)} kWh` : 'Não identificada'}<span className="subcell">{r.chemistry || 'Química não informada'}</span>{r.provenance?.capacity_kwh && <a className="source-link" href={r.provenance.capacity_kwh} target="_blank" rel="noreferrer">Fonte técnica <ExternalLink size={12}/></a>}</TableCell>
                            <TableCell><span className={`badge ${r.confidence === 'A' ? 'good' : 'warning'}`}>{r.confidence} · {r.confidence === 'A' ? 'Confirmada' : r.confidence === 'B' ? 'Provável' : 'Revisar'}</span></TableCell>
                          </TableRow>
                        ))}
                      </DataTable>
                      <div className="pagination"><span>Página {page + 1} de {Math.ceil(data.fleet.total / 25)}</span><Button variant="outline" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>Anterior</Button><Button variant="outline" disabled={(page + 1) * 25 >= data.fleet.total} onClick={() => setPage((p) => p + 1)}>Próxima</Button></div>
                    </>
                  ) : <Empty/>}
                </section>
              </TabsContent>
              <TabsContent value="batteries">
                <div className="two-columns">
                  <section className="panel"><h2>Química das baterias</h2><Chart items={s.by_chemistry} color={PALETTE.chemistry}/></section>
                  <section className="panel"><h2>Energia por modelo</h2><Chart items={s.by_model.filter((x: Row) => x.known_vehicles)} dataKey="energy_mwh" color={PALETTE.energy} unit="MWh"/></section>
                </div>
                <section className="panel"><div className="panel-heading"><div><span className="eyebrow">ENERGIA</span><h2>MWh por tipo de propulsão</h2></div><Zap/></div><PropulsionChart items={(s.energy_by_propulsion || propulsionItems).map((r: Row) => ({...r, name: PROPULSION[r.name] || r.name}))} dataKey="energy_mwh" unit="MWh"/><p className="caption">Híbrido usa pack pequeno (~1 kWh). Não compare esse MWh com o de um BEV sem olhar a propulsão.</p></section>
                <section className="panel">
                  <div className="panel-heading"><div><h2>Catálogo técnico validado</h2><p>Regras por versão, ano e propulsão. Catálogo independente dos filtros da frota. O código da peça fica disponível quando a fonte publica o part number.</p></div><Export report="batteries" query={query}/></div>
                  {data.batteries.map((b: Row) => (
                    <div className="battery-card" key={b.id}>
                      <BatteryCharging size={28}/>
                      <div>
                        <h3>{b.brand} {b.model} · {b.version}</h3>
                        <p>Aplicável a {b.year_start}–{b.year_end} · {PROPULSION[b.propulsion] || b.category || 'BEV'} · {b.technology || 'Tecnologia não informada'} · {b.chemistry || 'Química não validada'}{b.part_number ? ` · código ${b.part_number}` : ''}</p>
                      </div>
                      <strong>{num(b.capacity_kwh, 1)} <small>kWh</small></strong>
                      <span>Garantia: {b.warranty_years || '—'} anos{b.warranty_km ? ` ou ${count(b.warranty_km)} km` : ''}</span>
                      <a className="source-link" href={b.provenance.capacity_kwh} target="_blank" rel="noreferrer">Fonte <ExternalLink size={14}/></a>
                    </div>
                  ))}
                </section>
              </TabsContent>
              <TabsContent value="forecast">
                <section className="panel">
                  <div className="panel-heading">
                    <div><span className="eyebrow">CENÁRIOS ESTIMADOS</span><h2>Quando planejar a segunda vida?</h2><p>Ano do veículo + janela escolhida. Não considera desgaste individual.</p></div>
                    <div className="scenario-buttons">{['8', '10', '12'].map((v) => <Button key={v} variant={scenario === v ? 'default' : 'outline'} onClick={() => setScenario(v)}>{v} anos</Button>)}</div>
                  </div>
                  {data.forecast.items.length ? (
                    <div className="chart">
                      <ResponsiveContainer width="100%" height={290}>
                        <BarChart data={data.forecast.items}>
                          <CartesianGrid strokeDasharray="3 3" vertical={false}/>
                          <XAxis dataKey="year"/>
                          <YAxis tickFormatter={(v) => count(v)}/>
                          <Tooltip formatter={(v: any) => count(Number(v))}/>
                          <Bar dataKey="vehicles" name="Veículos na janela" fill="#126753" radius={[5, 5, 0, 0]}/>
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  ) : <Empty/>}
                  <div className="panel-heading"><p className="caption">{count(data.forecast.missing_year_vehicles)} veículos sem ano ficam fora das janelas. MWh nominais não estimam capacidade residual.</p><Export report="forecast" query={query}/></div>
                  <DataTable heads={['Ano da janela', 'Veículos', 'Energia calculada (MWh)', 'Com bateria identificada']}>
                    {data.forecast.items.map((r: Row) => <TableRow key={r.year}><TableCell>{r.year}</TableCell><TableCell>{count(r.vehicles)}</TableCell><TableCell>{num(r.energy_mwh, 2)}</TableCell><TableCell>{count(r.known_vehicles)}</TableCell></TableRow>)}
                  </DataTable>
                </section>
                <section className="panel">
                  <h2>Fim estimado da garantia</h2>
                  <p>{count(data.forecast.missing_warranty_vehicles)} veículos sem regra validada. O limite de quilometragem pode encerrar a cobertura antes do prazo.</p>
                  {data.forecast.warranty.length ? <Chart items={data.forecast.warranty.map((r: Row) => ({...r, name: String(r.year)}))} color={PALETTE.energy}/> : <Empty text="Sem garantia validada neste recorte."/>}
                </section>
              </TabsContent>
              <TabsContent value="monthly">
                <section className="panel">
                  <div className="panel-heading"><div><h2>Evolução mensal</h2><p>{month(data.monthly.previous_reference)} → {month(data.monthly.reference)}</p></div><Export report="monthly-change" query={query}/></div>
                  <SeriesChart items={data.series?.items || []}/>
                  <p className="caption">{data.series?.note} Emplacamentos Fenabrave: {(data.series?.registrations || []).map((r: Row) => `${PROPULSION[r.propulsion] || r.propulsion} ${count(r.quantity)}`).join(' · ') || 'ainda não importados.'}</p>
                  {data.monthly.available ? (
                    <>
                      <div className="change-total"><strong>{data.monthly.delta >= 0 ? '+' : ''}{count(data.monthly.delta)}</strong><span>variação líquida · {num(data.monthly.change_pct, 2)}%</span></div>
                      <p className="caption">Variação de estoque não equivale a novos emplacamentos. Mudanças acima de 30% são sinalizadas.</p>
                      <DataTable heads={['Modelo', 'Município', 'Anterior', 'Atual', 'Variação', 'Auditoria']}>
                        {data.monthly.items.slice(0, 100).map((r: Row, i: number) => (
                          <TableRow key={i}><TableCell>{r.brand} {r.model}</TableCell><TableCell>{r.city}/{r.uf}</TableCell><TableCell>{count(r.previous)}</TableCell><TableCell>{count(r.current)}</TableCell><TableCell>{r.delta > 0 ? '+' : ''}{count(r.delta)}</TableCell><TableCell>{r.new ? 'Novo no recorte' : r.disappeared ? 'Ausente no mês' : r.atypical ? 'Variação atípica' : '—'}</TableCell></TableRow>
                        ))}
                      </DataTable>
                      <p className="caption">Até 100 grupos exibidos. Exporte o relatório completo.</p>
                    </>
                  ) : <Empty text="Importe também o mês imediatamente anterior para comparar a evolução."/>}
                </section>
              </TabsContent>
              <TabsContent value="quality">
                <div className="two-columns">
                  <section className="panel"><h2>Qualidade das correspondências</h2><Chart items={data.quality.by_confidence} color={PALETTE.confidence}/><p className="caption">A: confirmada · B: provável · C: duvidosa · D: sem correspondência. Sem ano: {count(data.quality.missing_year_vehicles)} veículos; sem localização: {count(data.quality.missing_location_vehicles)}.</p></section>
                  <section className="panel">
                    <h2>Atualizar e salvar a frota</h2>
                    <p>Último mês salvo: <strong>{month(options.references?.[0])}</strong>. Ampliar famílias em src/catalog.py só entra no <strong>próximo</strong> mês publicado. “Sem novidade” significa que junho/julho já estão gravados e não serão reescritos.</p>
                    <label className="filter admin-key"><span>Chave de administração</span><input type="password" value={key} autoComplete="off" placeholder="Chave configurada no servidor" onChange={(e) => setKey(e.target.value)}/></label>
                    <div className="admin-actions"><Button disabled={!key || busy || running} onClick={() => admin('etl/run')}><RefreshCw size={16}/> Buscar mês mais recente</Button><Button variant="outline" disabled={!key || busy} onClick={() => admin('probe')}><Activity size={16}/> Testar APIs</Button></div>
                    {message && <p role="status" className="admin-message">{message}</p>}
                    <p className="caption">A chave está no arquivo .env, campo ADMIN_API_KEY. “Sem novidade” significa que o mês já está salvo.</p>
                  </section>
                </div>
                <section className="panel">
                  <h2>Cobertura vs frota oficial por combustível</h2>
                  <p>{s.official_coverage?.note}</p>
                  <p className="caption">Referência da régua: {month(s.official_coverage?.reference)}. Total oficial {count(s.official_coverage?.official_total)} · no recorte {count(s.vehicles)} ({num(s.official_coverage?.coverage_pct, 1)}%).</p>
                  <DataTable heads={['Propulsão', 'No catálogo', 'Oficial SENATRAN', 'Diferença', 'Cobertura']}>
                    {(s.official_coverage?.items || []).map((r: Row) => (
                      <TableRow key={r.propulsion}><TableCell>{PROPULSION[r.propulsion] || r.propulsion}</TableCell><TableCell>{count(r.catalog_vehicles)}</TableCell><TableCell>{count(r.official_vehicles)}</TableCell><TableCell>{r.gap == null ? '—' : count(r.gap)}</TableCell><TableCell>{num(r.coverage_pct, 1)}%</TableCell></TableRow>
                    ))}
                  </DataTable>
                </section>
                <section className="panel">
                  <h2>Fila de modelos não classificados</h2>
                  <p>{data.quality.unclassified_note} Com indício de eletrificação: {count(data.quality.unclassified_hint_vehicles)}. Sem indício (não catalogar): {count(data.quality.unclassified_other_vehicles)}.</p>
                  {data.quality.unclassified?.length ? (
                    <DataTable heads={['Nome na fonte', 'Veículos', 'Indício de eletrificação']}>
                      {data.quality.unclassified.map((r: Row, i: number) => (
                        <TableRow key={i}><TableCell>{r.raw_name}</TableCell><TableCell>{count(r.vehicles)}</TableCell><TableCell>{r.electrified_hint ? 'Sim' : 'Não'}</TableCell></TableRow>
                      ))}
                    </DataTable>
                  ) : <Empty text="Nenhum modelo excluído neste snapshot."/>}
                </section>
                <section className="panel">
                  <h2>Candidatos técnicos OpenEV para revisão</h2>
                  <p>Sobreposição com famílias do catálogo. Não aprovados automaticamente; o código da peça entra quando a evidência for aceita.</p>
                  {data.quality.technical_shortlist?.length ? (
                    <DataTable heads={['Marca', 'Modelo', 'Ano', 'kWh', 'Química']}>
                      {data.quality.technical_shortlist.slice(0, 25).map((r: Row) => (
                        <TableRow key={r.id}><TableCell>{r.brand}</TableCell><TableCell>{r.model}</TableCell><TableCell>{r.year || '—'}</TableCell><TableCell>{num(r.capacity_kwh, 1)}</TableCell><TableCell>{r.chemistry || '—'}</TableCell></TableRow>
                      ))}
                    </DataTable>
                  ) : <Empty text="Baixe a base OpenEV para gerar a fila de revisão."/>}
                  <div className="admin-actions"><Button disabled={!key || busy} onClick={() => admin('technical/download')}>Baixar e salvar base técnica OpenEV</Button></div>
                </section>
                <section className="panel">
                  <h2>Fontes e rastreabilidade</h2>
                  <div className="sources-grid">{data.sources.map((r: Row) => (
                    <article className="source-card" key={r.id}>
                      <span className="badge">{r.kind}</span><h3>{r.name}</h3>
                      <p>{r.details?.role || r.details?.scope}</p>
                      <small>{r.id === 'ibge' ? 'Base geográfica auxiliar' : dt(r.collected_at)}</small>
                      {r.months_late > 2 && <span className="badge warning">Referência atrasada: {r.months_late} meses</span>}
                      <a className="source-link" href={r.url} target="_blank" rel="noreferrer">Abrir fonte original <ExternalLink size={13}/></a>
                    </article>
                  ))}</div>
                </section>
                <section className="panel">
                  <h2>Estado das conexões</h2>
                  <label className="history-toggle"><input type="checkbox" checked={history} onChange={(e) => setHistory(e.target.checked)}/> Mostrar histórico completo de testes e processamento</label>
                  {data.quality.api_checks.length ? (
                    <DataTable heads={['Fonte', 'Resultado', 'Tempo', 'Verificado em', 'Detalhes']}>
                      {shownChecks.map((r: Row) => (
                        <TableRow key={r.id}><TableCell>{r.name}</TableCell><TableCell><span className={`badge ${r.ok ? 'good' : 'warning'}`}>{r.ok ? 'Conectada' : 'Falhou'} · {r.status_code || 'Sem HTTP'}</span></TableCell><TableCell>{count(r.duration_ms)} ms</TableCell><TableCell>{dt(r.checked_at)}</TableCell><TableCell className="details-cell">{r.details.error || r.details.note || `${count(r.details.response_bytes)} bytes recebidos`}</TableCell></TableRow>
                      ))}
                    </DataTable>
                  ) : <Empty text="Execute os testes para verificar as conexões."/>}
                </section>
                <section className="panel">
                  <h2>{history ? 'Histórico de processamento' : 'Última verificação da frota'}</h2>
                  {data.quality.runs.length ? (
                    <DataTable heads={['Referência', 'Status', 'Etapa', 'Linhas lidas', 'Grupos', 'Início / erro']}>
                      {shownRuns.map((r: Row) => (
                        <TableRow key={r.id}><TableCell>{r.reference || 'Mais recente'}</TableCell><TableCell><span className={`badge ${['SUCESSO', 'SEM_NOVIDADE'].includes(r.status) ? 'good' : 'warning'}`}>{({SUCESSO: 'Sucesso', SEM_NOVIDADE: 'Sem novidade', EXECUTANDO: 'Em andamento', ERRO: 'Erro', CANCELADO: 'Cancelado'} as Row)[r.status] || r.status}</span></TableCell><TableCell>{r.stage}</TableCell><TableCell>{count(r.raw_rows)}</TableCell><TableCell>{count(r.bev_rows)}</TableCell><TableCell className="details-cell">{dt(r.started_at)}{r.error && <span className="subcell">{r.error}</span>}</TableCell></TableRow>
                      ))}
                    </DataTable>
                  ) : <Empty text="A primeira atualização ainda não foi executada."/>}
                </section>
                <section className="panel">
                  <div className="panel-heading"><div><h2>Pendências de bateria</h2><p>{count(data.quality.missing_battery_vehicles)} veículos fora do cálculo de energia · até 100 grupos exibidos</p></div><Export report="data-quality" query={query}/></div>
                  {data.quality.pending.length ? (
                    <DataTable heads={['Nome na fonte', 'Ano', 'Veículos', 'Correspondência']}>
                      {data.quality.pending.slice(0, 100).map((r: Row, i: number) => <TableRow key={i}><TableCell>{r.raw_name}</TableCell><TableCell>{r.vehicle_year ?? 'Não informado'}</TableCell><TableCell>{count(r.vehicles)}</TableCell><TableCell>{r.confidence} · Revisão necessária</TableCell></TableRow>)}
                    </DataTable>
                  ) : <Empty text="Não há pendências no recorte atual."/>}
                </section>
              </TabsContent>
            </Tabs>
          </div>
        )}
        <footer><span><b>i9+</b> Baterias e Energia</span><span>Oficial: frota · Calculado: energia · Estimado: janelas futuras</span><span>Equipe 02 — Nexus</span></footer>
      </main>
    </div>
  );
}
