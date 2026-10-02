"""Copy an existing SQLite database to a NEW PostgreSQL database and reconcile IDs.

Never changes the source or switches application configuration automatically.
Usage: python -m scripts.migrate_registry --source data/i9-validated-v2.db --local
"""
import argparse
import json
import os
from pathlib import Path
from datetime import datetime,timezone
from sqlalchemy import create_engine,select,insert,func,inspect,text
from sqlalchemy.engine import URL
from src import db,intelligence_schema,operational_schema,auth_schema,pipeline_schema

def migrate(source,target_url):
    source_engine=create_engine('sqlite:///'+str(Path(source).resolve()))
    target=create_engine(target_url)
    db.meta.create_all(target)
    existing_tables=set(inspect(source_engine).get_table_names())
    report={'started_at':datetime.now(timezone.utc).isoformat(),'source':str(Path(source).resolve()),'tables':[]}
    for table in db.meta.sorted_tables:
        if table.name not in existing_tables:continue
        source_columns={col['name'] for col in inspect(source_engine).get_columns(table.name)}
        columns=[col for col in table.c if col.name in source_columns]
        with source_engine.connect() as src,target.begin() as dst:
            expected=src.execute(select(func.count()).select_from(table)).scalar()
            current=dst.execute(select(func.count()).select_from(table)).scalar()
            if current and current!=expected:raise RuntimeError(f'Destino não vazio/divergente: {table.name}. Use banco novo.')
            if not current:
                result=src.execute(select(*columns)).mappings()
                while rows:=result.fetchmany(1000):dst.execute(insert(table),[dict(r) for r in rows])
            actual=dst.execute(select(func.count()).select_from(table)).scalar()
            if expected!=actual:raise RuntimeError('Contagem divergente: '+table.name)
            for col in table.primary_key.columns:
                if str(col.type)=='INTEGER':
                    sequence=dst.execute(text('SELECT pg_get_serial_sequence(:tbl,:col)'),{'tbl':table.name,'col':col.name}).scalar()
                    if sequence:dst.execute(text('SELECT setval(CAST(:seq AS regclass), :value, :called)'),{'seq':sequence,'value':max(1,dst.execute(select(func.max(col))).scalar() or 1),'called':bool(actual)})
            report['tables'].append({'table':table.name,'source':expected,'target':actual})
        print(f'{table.name}: {actual}',flush=True)
    db.engine=target
    from src import fleet_publication,pipeline
    report['registry']=fleet_publication.migrate_legacy_registry()
    pipeline.initialize()
    report['finished_at']=datetime.now(timezone.utc).isoformat()
    dest=Path('data/migration');dest.mkdir(parents=True,exist_ok=True)
    (dest/'reconciliation.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    return report

def local_url(database='i9'):
    config=json.loads(Path('data/runtime/local-postgres.json').read_text())
    return URL.create('postgresql+psycopg',username='i9',password=config['password'],host='127.0.0.1',port=config['port'],database=database)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source',required=True);parser.add_argument('--local',action='store_true');args=parser.parse_args()
    if args.local:
        url=local_url()
        admin=create_engine(local_url('postgres'),isolation_level='AUTOCOMMIT')
        with admin.connect() as c:
            if not c.execute(text("SELECT 1 FROM pg_database WHERE datname='i9'")).first():c.execute(text('CREATE DATABASE i9'))
    else:
        url=os.environ.get('I9_MIGRATION_TARGET_URL')
        if not url:parser.error('Configure I9_MIGRATION_TARGET_URL ou use --local')
    migrate(args.source,url)

if __name__=='__main__':main()
