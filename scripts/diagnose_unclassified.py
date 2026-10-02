"""Prioritize SENATRAN names still outside FAMILIES against the official fuel gaps."""
import json
from pathlib import Path
from sqlalchemy import select, func
from src.db import engine, unclassified, snapshots, fleet
from src.connectors.fuel import coverage

ROOT = Path(__file__).resolve().parents[1]

def main():
    with engine.connect() as c:
        reference = c.execute(select(func.max(snapshots.c.reference))).scalar()
        if not reference:
            print('Nenhum snapshot publicado.')
            return
        rows = [dict(r) for r in c.execute(select(unclassified).where(unclassified.c.reference == reference).order_by(unclassified.c.vehicles.desc())).mappings()]
        catalog = {k: int(v) for k, v in c.execute(select(fleet.c.propulsion, func.sum(fleet.c.quantity)).where(fleet.c.reference == reference).group_by(fleet.c.propulsion)) if k}
    official = coverage(catalog)
    hint = [r for r in rows if r['electrified_hint']]
    other = [r for r in rows if not r['electrified_hint']]
    report = {
        'reference': reference,
        'unclassified_groups': len(rows),
        'hint_vehicles': sum(r['vehicles'] for r in hint),
        'other_vehicles': sum(r['vehicles'] for r in other),
        'official_coverage': official,
        'priority_prefixes': [{'raw_name': r['raw_name'], 'vehicles': r['vehicles']} for r in hint[:50]],
        'do_not_catalog': [{'raw_name': r['raw_name'], 'vehicles': r['vehicles']} for r in other[:20]],
        'note': 'Só catalogar nomes inequívocos da lista priority_prefixes. other_vehicles mistura ICE. Meta = official_coverage, não ABVE.' + ('' if rows else ' Snapshot sem fila gravada (ingestões antigas); a fila aparece em meses processados após modelo_nao_classificado.'),
    }
    out = ROOT / 'data' / 'staging' / f'unclassified-{reference}.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('reference', 'unclassified_groups', 'hint_vehicles', 'other_vehicles', 'note')}, ensure_ascii=False, indent=2))
    print('Fila completa:', out)

if __name__ == '__main__':
    main()
