import httpx
from sqlalchemy import select, update
from src import on_demand, pipeline, pipeline_schema as schema, senatran_months


def wait_idle():
    thread = on_demand._thread
    if thread:
        thread.join(timeout=10)
        assert not thread.is_alive(), 'Runner did not exit after the requested work'
    assert on_demand._thread is None


def test_start_checks_once_and_does_not_schedule(database, monkeypatch):
    calls = []
    monkeypatch.setattr(senatran_months, 'refresh_catalog', lambda: calls.append('catalog') or {})
    def forbidden(*args):
        raise AssertionError('No periodic scheduling in on-demand mode')
    monkeypatch.setattr(pipeline, 'schedule_due', forbidden)
    try:
        on_demand.start()
        wait_idle()
        assert calls == ['catalog']
        with database.connect() as c:
            jobs = list(c.execute(select(schema.job)).mappings())
        assert len(jobs) == 1 and jobs[0]['status'] == 'complete'
        on_demand.stop()
        on_demand.start()
        wait_idle()
        assert calls == ['catalog', 'catalog']
    finally:
        on_demand.stop()


def test_new_request_wakes_idle_runner_and_pending_work_is_recovered(database, monkeypatch):
    calls = []
    monkeypatch.setattr(senatran_months, 'refresh_catalog', lambda: calls.append('catalog') or {})
    pipeline.enqueue('catalog_refresh', {}, 'recover')
    try:
        on_demand.start(check_catalog=False)
        wait_idle()
        assert calls == ['catalog']
        pipeline.enqueue('catalog_refresh', {}, 'manual-check')
        on_demand.notify()
        wait_idle()
        assert calls == ['catalog', 'catalog']
        on_demand.stop()
        on_demand.notify()
        assert on_demand._thread is None
    finally:
        on_demand.stop()


def test_legacy_discovery_only_refreshes_catalog_in_desktop_mode(database, monkeypatch):
    calls = []
    monkeypatch.setenv('I9_ON_DEMAND_WORKER', 'true')
    monkeypatch.setattr(senatran_months, 'refresh_catalog', lambda: calls.append('catalog') or {})
    def forbidden(**kwargs):
        raise AssertionError('Legacy discovery must not enqueue downloads')
    monkeypatch.setattr(pipeline, 'discover', forbidden)
    pipeline.enqueue('discover', {'start': '2026-01'}, 'legacy-scheduled-discovery')
    try:
        on_demand.start(check_catalog=False)
        wait_idle()
        assert calls == ['catalog']
        with database.connect() as c:
            jobs = list(c.execute(select(schema.job)).mappings())
        assert len(jobs) == 1 and jobs[0]['status'] == 'complete'
    finally:
        on_demand.stop()


def test_catalog_failure_stops_runner_and_does_not_schedule_retry(database, monkeypatch):
    def unavailable(*args):
        httpx.Response(503, request=httpx.Request('GET', 'https://example.test/catalog')).raise_for_status()
    monkeypatch.setattr(pipeline, 'catalog_resources', unavailable)
    try:
        on_demand.start()
        wait_idle()
        jobs = pipeline.list_jobs()
        assert len(jobs) == 1 and jobs[0]['status'] == 'failed'
        assert 'HTTP 503' in jobs[0]['error'] and 'developer.mozilla' not in jobs[0]['error']
        result = senatran_months.months()
        assert result['refresh_status'] == 'failed' and result['attempted_at']
        assert result['checked_at'] is None
        assert senatran_months.request_refresh()['id'] == jobs[0]['id']
    finally:
        on_demand.stop()


def test_upgrade_retires_only_legacy_catalog_retry_waits(database):
    old = pipeline.enqueue('catalog_refresh', {}, 'old-retry')
    remote = pipeline.enqueue('import_remote', {'reference': '2026-01'}, 'remote-retry')
    with database.begin() as c:
        c.execute(update(schema.job).values(attempt_count=1, error='503'))
    senatran_months.retire_catalog_retries()
    assert pipeline.get_job(old['id'])['status'] == 'failed'
    assert pipeline.get_job(remote['id'])['status'] == 'queued'
