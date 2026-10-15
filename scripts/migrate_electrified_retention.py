"""Audit and optionally remove legacy full-fleet retained data.

Run without --apply first. Stop API/worker before applying to an existing DB.
"""
import argparse
import json
from pathlib import Path

from sqlalchemy import delete, func, select, update
from src import db, intelligence_schema as s, operational_schema as o, pipeline_schema as p
from src.pipeline import normalize


def within(path, folder):
    resolved = Path(path).resolve()
    return resolved if resolved.is_relative_to((db.ROOT / folder).resolve()) else None


def audit():
    with db.engine.connect() as c:
        summary = c.execute(select(func.count(), func.coalesce(func.sum(p.filtered_summary.c.quantity), 0))).one()
        heavy = c.execute(select(func.count()).select_from(o.heavy_stat)).scalar_one()
        artifacts = [r[0] for r in c.execute(select(p.artifact.c.path).distinct())]
        reports = [dict(r) for r in c.execute(select(s.source_snapshot).where(s.source_snapshot.c.method == 'official_workbook')).mappings()]
    return {'legacy_summary_rows': summary[0], 'legacy_summary_quantity': summary[1],
            'heavy_stat_rows': heavy, 'raw_artifacts': len(artifacts), 'reports': len(reports)}


def apply():
    raw_files = []
    report_files = []
    with db.engine.begin() as c:
        for path, in c.execute(select(p.artifact.c.path).distinct()):
            target = within(path, 'data/raw/pipeline') if path else None
            if target: raw_files.append(target)
        # Keep only possible electrified names for review, without fleet totals.
        c.execute(delete(p.filtered_summary).where(p.filtered_summary.c.electrified_hint == 0))
        c.execute(update(p.filtered_summary).values(quantity=0, row_count=0))
        c.execute(delete(o.heavy_stat))
        for source in c.execute(select(s.source_snapshot).where(s.source_snapshot.c.provider == 'SENATRAN')).mappings():
            meta = dict(source['metadata'] or {})
            if source['method'] == 'official_workbook' and meta.get('rows_path'):
                target = within(meta['rows_path'], 'data/processed/senatran')
                if target:report_files.append((source['id'], target, 'COMBUSTIVEL' in normalize(meta.get('name') or '')))
            c.execute(update(s.source_snapshot).where(s.source_snapshot.c.id == source['id']).values(raw_storage_path=None))
        for key in ('backup',):c.execute(delete(o.setting).where(o.setting.c.key == key))
    for source_id,path,is_fuel in report_files:
        if not path.is_file():continue
        if not is_fuel:
            path.unlink()
            with db.engine.begin() as c:
                source=c.execute(select(s.source_snapshot).where(s.source_snapshot.c.id==source_id)).mappings().one()
                meta=dict(source['metadata'] or {});meta.update(scope='metadata_only',rows_path=None)
                c.execute(update(s.source_snapshot).where(s.source_snapshot.c.id==source_id).values(record_count=0,metadata=meta))
            continue
        temp=path.with_suffix('.electrified.part')
        kept=0;fuel_index=None
        with path.open(encoding='utf-8') as original,temp.open('w',encoding='utf-8') as out:
            for line in original:
                item=json.loads(line);values=item['values']
                if fuel_index is None:
                    header=[normalize(str(v or '')) for v in values]
                    if 'COMBUSTIVEL VEICULO' not in header:continue
                    fuel_index=header.index('COMBUSTIVEL VEICULO');out.write(line);kept+=1;continue
                if fuel_index<len(values) and ('ELETRIC' in normalize(str(values[fuel_index] or '')) or 'HIBRIDO' in normalize(str(values[fuel_index] or ''))):
                    out.write(line);kept+=1
        temp.replace(path)
        with db.engine.begin() as c:
            source=c.execute(select(s.source_snapshot).where(s.source_snapshot.c.id==source_id)).mappings().one()
            meta=dict(source['metadata'] or {});meta['scope']='electrified_fuel_only'
            c.execute(update(s.source_snapshot).where(s.source_snapshot.c.id==source_id).values(record_count=kept,metadata=meta))
    for path in set(raw_files):path.unlink(missing_ok=True)
    return audit()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true',help='Remove dados legados após parar API e trabalhador')
    args=parser.parse_args()
    print(json.dumps(apply() if args.apply else audit(),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
