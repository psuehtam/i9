export type Row = Record<string, any>;

export const num = (v: number | null | undefined, d = 0) =>
  v == null ? '—' : v.toLocaleString('pt-BR', {maximumFractionDigits: d, minimumFractionDigits: d > 0 ? 0 : 0});

export const count = (v: number | null | undefined) => num(v, 0);

export const month = (v?: string) =>
  v ? new Date(v + '-15T12:00:00').toLocaleDateString('pt-BR', {month: 'long', year: 'numeric'}) : 'Sem referência';

export const dt = (v?: string) => (v ? new Date(v).toLocaleString('pt-BR') : 'Ainda não coletada');

export const PROPULSION: Record<string, string> = {
  BEV: 'Elétrico puro',
  PHEV: 'Híbrido plug-in',
  HEV: 'Híbrido',
  HEV_FLEX: 'Híbrido flex',
  FCEV: 'Célula a combustível',
  MHEV_12V: 'MHEV 12 V',
  MHEV_48V: 'MHEV 48 V',
  ELECTRIFIED: 'Eletrificados (ABVE)',
  UNKNOWN: 'Não informado',
};

export const ROLE: Record<string, string> = {
  public_user: 'Consulta pública',
  analyst: 'Analista',
  data_engineer: 'Engenharia de dados',
  partner: 'Parceiro',
  authorized_vehicle_lookup: 'Consulta autorizada',
  admin: 'Administração',
};

export const PALETTE = {
  uf: '#126753',
  brand: '#3b6ea8',
  city: '#c47b2b',
  chemistry: '#7a4ea3',
  energy: '#3976ae',
  confidence: '#b87f2d',
  bev: '#126753',
  phev: '#3b6ea8',
  hev: '#c47b2b',
};

export async function apiGet(path: string, signal?: AbortSignal): Promise<any> {
  const r = await fetch(path, {signal});
  if (!r.ok) {
    const e: any = await r.json().catch(() => ({}));
    throw Error(typeof e.detail === 'string' ? e.detail : `Falha na consulta (${r.status}).`);
  }
  return r.json();
}
