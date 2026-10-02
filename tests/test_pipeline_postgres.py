"""Integration tests against a disposable PostgreSQL database, never SQLite.

Set I9_TEST_DATABASE_URL to an explicitly disposable database. Each test uses
an isolated schema and independent connections; no application tables are reset.
"""
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select, update, text, func
from src import db, pipeline as q, pipeline_schema as p, intelligence_schema as s


@pytest.fixture
def postgres(monkeypatch, tmp_path):
    url = os.getenv('I9_TEST_DATABASE_URL')
    if not url:
        pytest.skip('I9_TEST_DATABASE_URL não configurada; exige PostgreSQL real')
    admin = create_engine(url)
    assert admin.dialect.name == 'postgresql'
    schema = 'pipeline_test_' + uuid.uuid4().hex
    with admin.begin() as c:
        c.execute(text(f'CREATE SCHEMA {schema}'))
    engine = create_engine(url, connect_args={'options': f'-csearch_path={schema}'}, pool_size=5)
    db.meta.create_all(engine)
    monkeypatch.setattr(db, 'engine', engine)
    monkeypatch.setattr(db, 'ROOT', tmp_path)
    q.initialize()
    yield engine
    engine.dispose()
    with admin.begin() as c:
        c.execute(text(f'DROP SCHEMA {schema} CASCADE'))
    admin.dispose()


def test_two_workers_claim_one_job_using_independent_connections(postgres, monkeypatch):
    job = q.enqueue('discover', {}, 'concurrent')
    barrier = threading.Barrier(2, timeout=10)
    original = q._epoch
    def sync(c):
        value = original(c)
        barrier.wait()
        return value
    monkeypatch.setattr(q, '_epoch', sync)
    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(q.claim, 'worker-a')
        b = pool.submit(q.claim, 'worker-b')
        results = [a.result(timeout=15), b.result(timeout=15)]
    claimed = [value for value in results if value]
    assert len(claimed) == 1
    assert claimed[0]['job_id'] == job['id']
    assert q.get_job(job['id'])['attempt_count'] == 1


def test_locked_job_is_skipped_and_expired_worker_is_fenced(postgres):
    job = q.enqueue('discover', {}, 'skip-locked')
    with postgres.begin() as locked:
        locked.execute(select(p.job).where(p.job.c.id == job['id']).with_for_update()).one()
        with ThreadPoolExecutor(max_workers=1) as pool:
            assert pool.submit(q.claim, 'contender').result(timeout=10) is None
    old = q.claim('old')
    with postgres.begin() as c:
        c.execute(update(p.job).where(p.job.c.id == job['id']).values(
            lease_until=q.timestamp(datetime.now(timezone.utc) - timedelta(seconds=1))))
    new = q.claim('new')
    with ThreadPoolExecutor(max_workers=1) as pool:
        with pytest.raises(q.LeaseLost):
            pool.submit(q.finish, old, {'invalid': True}).result(timeout=10)
    q.finish(new, {'valid': True})
    assert q.get_job(job['id'])['result'] == {'valid': True}


def test_real_postgres_parse_classify_and_resume_atomic_block(postgres, tmp_path, monkeypatch):
    path = tmp_path / 'senatran.csv'
    path.write_text('UF;MUNICIPIO;MARCA MODELO;ANO FABRICACAO;QUANTIDADE\n'
                    'PR;Curitiba;I/BYD DOLPHIN GS;2026;90\n'
                    'SP;São Paulo;I/TOYOTA COROLLA;2025;20\n', encoding='utf-8')
    q.enqueue('import_file', {'path': str(path), 'reference': '2026-01'}, 'pg-parse')
    lease = q.claim('worker')
    artifact = q.register_artifact(path, '2026-01', lease)
    original = q._persist_filtered_chunk
    def lost_response(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError('commit completed; network response lost')
    monkeypatch.setattr(q, '_persist_filtered_chunk', lost_response)
    with pytest.raises(RuntimeError):
        q.parse_artifact(artifact['id'], lease)
    monkeypatch.setattr(q, '_persist_filtered_chunk', original)
    content_id = q.parse_artifact(artifact['id'], lease)
    source_id, _ = q.classify_content(content_id, lease)
    with postgres.connect() as c:
        assert c.execute(select(func.count()).select_from(p.observation)).scalar_one() == 1
        assert c.execute(select(func.sum(s.aggregate.c.quantity)).where(s.aggregate.c.source_snapshot_id == source_id)).scalar_one() == 90
        assert c.execute(select(s.source_snapshot.c.metadata).where(s.source_snapshot.c.id == source_id)).scalar_one()['pending_quantity'] == 20


def test_concurrent_enqueue_keeps_single_logical_job(postgres):
    start = threading.Barrier(2, timeout=10)
    def submit():
        start.wait()
        return q.enqueue('import_file', {'path': 'fixture.csv', 'reference': '2026-01'}, 'same-key')
    with ThreadPoolExecutor(max_workers=2) as pool:
        a, b = pool.submit(submit), pool.submit(submit)
        first, second = a.result(timeout=15), b.result(timeout=15)
    assert first['id'] == second['id']
    assert first['generation'] == second['generation'] == 1
