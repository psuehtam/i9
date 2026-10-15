"""Discover, download and process exactly one SENATRAN competence."""
from __future__ import annotations

import argparse
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from sqlalchemy import select

from src import db, pipeline, pipeline_schema as schema


TERMINAL = {'complete', 'failed', 'paused'}
REMOTE_KINDS = {'import_remote', 'heavy_stats_remote', 'official_report_remote'}


def validate_reference(value: str) -> str:
    try:
        parsed = datetime.strptime(value, '%Y-%m')
    except ValueError as exc:
        raise argparse.ArgumentTypeError('use o formato AAAA-MM, por exemplo 2026-08') from exc
    if parsed.strftime('%Y-%m') != value:
        raise argparse.ArgumentTypeError('use o formato AAAA-MM, por exemplo 2026-08')
    return value


def jobs_for_reference(reference: str) -> list[dict]:
    with db.engine.connect() as connection:
        rows = connection.execute(
            select(schema.job)
            .where(schema.job.c.kind.in_(REMOTE_KINDS))
            .order_by(schema.job.c.created_at.desc(), schema.job.c.id)
        ).mappings()
        result = []
        seen = set()
        for row in rows:
            item = dict(row)
            if (item.get('payload') or {}).get('reference') != reference:
                continue
            # Keep only the newest execution for each dataset.
            identity = (item['kind'], item['payload'].get('report_id'))
            if identity in seen:
                continue
            seen.add(identity)
            result.append(item)
        return result


def progress_text(job: dict) -> str:
    progress = job.get('progress') or {}
    stage = job.get('stage') or job.get('status') or 'aguardando'
    downloaded = progress.get('downloaded_bytes')
    total = progress.get('download_bytes')
    if isinstance(downloaded, int) and isinstance(total, int) and total > 0:
        percent = min(100, downloaded * 100 / total)
        return f'{stage}: {percent:5.1f}% ({downloaded / 1048576:.1f}/{total / 1048576:.1f} MiB)'
    created = progress.get('materialized_units')
    planned = progress.get('planned_units')
    if isinstance(created, int) and isinstance(planned, int) and planned > 0:
        percent = min(100, created * 100 / planned)
        return f'{stage}: {percent:5.1f}% ({created:,}/{planned:,} cadastros)'
    scanned = progress.get('scanned_rows')
    if isinstance(scanned, int):
        return f'{stage}: {scanned:,} linhas lidas'
    return stage


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Baixar e processar uma única competência mensal da SENATRAN.'
    )
    parser.add_argument('--reference', required=True, type=validate_reference,
                        help='competência fechada no formato AAAA-MM')
    parser.add_argument('--refresh', action='store_true',
                        help='verificar uma nova revisão mesmo se o mês já estiver concluído')
    args = parser.parse_args()

    if os.getenv('ALLOW_SOURCE_DOWNLOAD', 'false').lower() != 'true':
        parser.error('configure ALLOW_SOURCE_DOWNLOAD=true no .env antes de baixar')

    db.init_db()
    pipeline.initialize()
    print(f'Consultando a SENATRAN para {args.reference}...', flush=True)
    from src.senatran_months import refresh_catalog, request_import
    refresh_catalog()
    try:
        requested = request_import(args.reference, args.refresh, f'cli:{args.reference}:{pipeline.timestamp()}')
    except Exception as exc:
        print(getattr(exc, 'detail', str(exc)), file=sys.stderr)
        return 3
    target_ids = set(requested['job_ids'])
    jobs = jobs_for_reference(args.reference)
    active = [item for item in jobs if item['status'] in {'queued', 'running'}]
    target_ids.update(item['id'] for item in active)
    if not target_ids:
        print(f'{args.reference} ja estava importado; nenhum arquivo foi baixado novamente.')
        return 0

    last_lines: dict[str, str] = {}
    owner = f'manual-month:{os.getpid()}'
    executor = ThreadPoolExecutor(max_workers=1)
    task = None
    while True:
        current = {job_id: pipeline.get_job(job_id) for job_id in target_ids}
        missing_ids = target_ids - set(current)
        if missing_ids:
            print('Execução não encontrada no banco: ' + ', '.join(sorted(missing_ids)), file=sys.stderr)
            return 5

        for job_id in sorted(target_ids):
            job = current[job_id]
            label = 'marca/modelo' if job['kind'] == 'import_remote' else 'tipo/espécie/eixos'
            line = f'[{label}] {job["status"]} — {progress_text(job)}'
            if last_lines.get(job_id) != line:
                print(line, flush=True)
                last_lines[job_id] = line

        if all(item['status'] in TERMINAL for item in current.values()):
            failed = [item for item in current.values() if item['status'] != 'complete']
            if failed:
                for item in failed:
                    print(f'Falha em {item["kind"]}: {item.get("error") or item["status"]}', file=sys.stderr)
                return 6
            print(f'Competência {args.reference} concluída com sucesso.')
            return 0

        # Claim only jobs selected above. A regular worker may process one first;
        # in that case this call simply returns None and the next poll observes it.
        ready = next((item for item in current.values() if item['status'] == 'queued'), None)
        if task is not None and task.done():
            task.result()
            task = None
        if ready and task is None:
            task = executor.submit(pipeline.run_once, owner=owner, job_id=ready['id'])
        time.sleep(2)


if __name__ == '__main__':
    raise SystemExit(main())
