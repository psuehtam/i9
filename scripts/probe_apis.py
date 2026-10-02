"""Run real HTTP probes and keep a machine-readable evidence report."""
import json
from concurrent.futures import ThreadPoolExecutor
from src.db import init_db, ROOT
from src.connectors.public import probe, CATALOG, IBGE, OPENEV, GITHUB, catalog

def main():
    init_db()
    targets=[('SENATRAN catálogo',CATALOG),('IBGE municípios',IBGE),('OpenEV GitHub',GITHUB)]
    with ThreadPoolExecutor(max_workers=5) as pool:
        results=list(pool.map(lambda x:probe(*x),targets))
    (ROOT/'docs/api-live-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    for r in results:print(f"{r['name']}: HTTP {r['status_code']} | {'OK' if r['ok'] else 'FALHOU'} | {r['duration_ms']} ms")

if __name__=='__main__':main()
