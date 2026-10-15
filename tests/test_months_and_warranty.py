from datetime import date, datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi import HTTPException
from sqlalchemy import insert, select, update, func
from src import pipeline as p, pipeline_schema as ps, senatran_months as months
from src import intelligence_schema as s, battery_status as status, registry_service
from test_registry import account
from test_pipeline_postgres import postgres


RESOURCES = [{'id':'one','name':'MARCA MODELO','url':'https://example.test/2026-01.csv','description':'2026-01'}]


def test_refresh_reuses_pending_even_across_time_buckets(database):
    first = months.request_refresh()
    with database.begin() as c:
        c.execute(update(ps.job).where(ps.job.c.id == first['id']).values(created_at='2026-01-01', updated_at='2026-01-01'))
    assert months.request_refresh()['id'] == first['id']
    assert months.request_refresh(startup=True)['id'] == first['id']
    with database.begin() as c:
        c.execute(update(ps.job).where(ps.job.c.id == first['id']).values(status='failed', updated_at=p.timestamp()))
    assert months.request_refresh()['id'] == first['id']
    with database.begin() as c:
        c.execute(update(ps.job).where(ps.job.c.id == first['id']).values(updated_at=p.timestamp(datetime.now(timezone.utc)-timedelta(minutes=2))))
    assert months.request_refresh()['id'] != first['id']


def test_concurrent_catalog_requests_share_one_job(postgres):
    with ThreadPoolExecutor(max_workers=4) as executor:
        ids = list(executor.map(lambda _: months.request_refresh()['id'], range(8)))
    assert len(set(ids)) == 1


def test_catalog_is_read_only_and_retains_last_success(database, monkeypatch):
    months.refresh_catalog(RESOURCES)
    with database.connect() as c:
        assert c.execute(select(func.count()).select_from(ps.job)).scalar() == 0
    original = months.months()
    def fail(*args): raise RuntimeError('fonte indisponivel')
    monkeypatch.setattr(p, 'catalog_resources', fail)
    with pytest.raises(RuntimeError): months.refresh_catalog()
    assert months.months()['items'] == original['items']
    assert months.months()['checked_at'] == original['checked_at']
    assert months.months()['last_error'] == 'fonte indisponivel'


def test_daily_discovery_with_downloads_paused(database, monkeypatch):
    monkeypatch.setenv('I9_UPDATES_PAUSED', 'true')
    monkeypatch.setenv('I9_CATALOG_AUTO_REFRESH', 'true')
    at = datetime(2026, 9, 24, tzinfo=timezone.utc)
    assert p.schedule_due(at) == p.schedule_due(at)
    with database.connect() as c:
        jobs = list(c.execute(select(ps.job)).mappings())
    assert len(jobs) == 1 and jobs[0]['kind'] == 'catalog_refresh'


def test_month_permissions_idempotency_and_paused_automation(client, database, monkeypatch):
    monkeypatch.setenv('I9_UPDATES_PAUSED', 'true')
    monkeypatch.setenv('ALLOW_SOURCE_DOWNLOAD', 'true')
    months.refresh_catalog(RESOURCES)
    body = {'reference':'2026-01','idempotency_key':'first'}
    path = '/api/v3/admin/senatran/import'
    assert client.post(path,json=body).status_code == 401
    headers = account(client)
    assert client.post(path,json=body).status_code == 403
    first = client.post(path,json=body,headers=headers)
    assert first.status_code == 202, first.text
    assert client.post(path,json=body,headers=headers).json() == first.json()
    assert client.post(path,json={**body,'idempotency_key':'second'},headers=headers).json() == first.json()
    assert client.post(path,json={**body,'reference':'2099-01'},headers=headers).status_code == 422
    assert client.post(path,json={**body,'reference':'2026-02'},headers=headers).status_code == 409


def test_ambiguous_resources_block_import(database, monkeypatch):
    monkeypatch.setenv('ALLOW_SOURCE_DOWNLOAD', 'true')
    months.refresh_catalog(RESOURCES + [{**RESOURCES[0], 'url':'https://example.test/2026-01-other.csv'}])
    with pytest.raises(HTTPException) as exc: months.request_import('2026-01', False, 'a')
    assert exc.value.status_code == 409


def test_concurrent_imports_share_jobs(postgres, monkeypatch):
    monkeypatch.setenv('ALLOW_SOURCE_DOWNLOAD', 'true')
    months.refresh_catalog(RESOURCES)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda key: months.request_import('2026-01',False,key), ['a','b']))
    assert results[0]['job_ids'] == results[1]['job_ids']
    with postgres.connect() as c:
        assert c.execute(select(func.count()).select_from(ps.job)).scalar() == 1


def seed_battery(database):
    with database.begin() as c:
        c.execute(insert(s.source_snapshot).values(id='battery-source',provider='fixture',access_level='public'))
        c.execute(insert(s.battery_model).values(id='model-test',source_snapshot_id='battery-source',warranty_years=8,
                    warranty_km=160000,expected_cycle_life=1000,automotive_eol_threshold_percent=70,field_sources={'warranty_years':'manual'}))
        c.execute(insert(s.battery_asset).values(id='bat',source_snapshot_id='battery-source',battery_model_id='model-test',current_status='in_use'))
        for n in (1,2):
            c.execute(insert(s.vehicle_asset).values(id=f'vehicle-{n}',source_snapshot_id='battery-source'))
            c.execute(insert(s.installation).values(id=f'install-{n}',battery_id='bat',vehicle_id=f'vehicle-{n}',source_snapshot_id='battery-source',
                         installed_at='2026-01-01T00:00:00+00:00' if n == 1 else '2026-02-01T00:00:00+00:00',
                         removed_at='2026-02-01T00:00:00+00:00' if n == 1 else None))


def test_calendar_boundaries():
    assert status.add_months(date(2024,1,31),1) == date(2024,2,29)
    assert status.add_months(date(2024,2,29),12) == date(2025,2,28)
    with pytest.raises(HTTPException): status.validate({'start_date':'2026-01-01','duration_months':12,'end_date':'2028-01-01'})


def test_warranty_api_conflicts_and_no_automatic_application(client, database):
    seed_battery(database)
    path = '/api/v3/batteries/bat/warranty'
    initial = client.get(path).json()
    assert initial['warranty']['term_status'] == 'unknown'
    assert initial['warranty']['suggestion']['years'] == 8
    body = {'revision':0,'start_date':'2025-01-31','duration_months':1,'evidence':'manual brasileiro'}
    assert client.put(path,json=body).status_code == 401
    headers = account(client)
    assert client.put(path,json=body).status_code == 403
    assert client.put(path,json=body,headers=headers).status_code == 200
    assert client.put(path,json=body,headers=headers).status_code == 409
    result = client.get(path).json()
    assert result['warranty']['end_date'] == '2025-02-28'
    assert result['warranty']['term_status'] == 'expired'
    assert client.get('/api/v3/batteries/bat').json()['battery']['current_status'] == 'in_use'
    assert client.get('/api/v3/admin/battery-alerts').json()['items'][0]['reasons'] == ['expired']


def test_90_days_and_partial_warranty(database):
    seed_battery(database)
    with database.begin() as c:
        c.execute(insert(s.warranty).values(battery_id='bat',revision=1,data={'end_date':'2026-04-01'},updated_at='2026-01-01'))
        result = status.summary(c,'bat',date(2026,1,1))
        assert result['warranty']['days_remaining'] == 90
        assert result['warranty']['term_status'] == 'expiring'
        assert status.summary(c,'bat',date(2025,12,31))['warranty']['term_status'] == 'within_term'
        assert result['warranty']['km_status'] == 'unknown'


def test_odometer_scoped_to_installation_and_chronology(client, database):
    seed_battery(database)
    headers = account(client)
    path = '/api/v3/batteries/bat/events'
    def event(installation,when,km):
        return client.post(path,headers=headers,json={'installation_id':installation,'observed_at':when,'odometer_km':km,'evidence':'leitura oficina'})
    assert event('install-1','2026-01-15T00:00:00Z',90000).status_code == 200
    assert event('install-2','2026-02-15T00:00:00Z',10000).status_code == 200
    assert event('install-2','2026-02-10T00:00:00Z',11000).status_code == 422
    assert event('install-1','2026-02-15T00:00:00Z',91000).status_code == 422
    warranty={'revision':0,'installation_id':'install-2','km_limit':10000,'km_basis':'absolute','evidence':'manual oficina'}
    assert client.put('/api/v3/batteries/bat/warranty',headers=headers,json=warranty).status_code == 200
    summary = client.get('/api/v3/batteries/bat').json()
    assert summary['warranty']['km_status'] == 'limit_reached'
    assert summary['warranty']['km_remaining'] == 0


def test_latest_health_value_keeps_measurement_date(client, database):
    seed_battery(database)
    headers = account(client)
    path = '/api/v3/batteries/bat/events'
    for when,fields in [('2026-02-01',{'soh_percent':65}),('2026-03-01',{'cycle_count':1100}),('2026-01-01',{'soh_percent':90})]:
        assert client.post(path,headers=headers,json={'observed_at':when+'T00:00:00Z','evidence':'oficina teste',**fields}).status_code == 200
    health = client.get('/api/v3/batteries/bat').json()['health']
    assert health['soh_percent'] == 65
    assert health['soh_observed_at'].startswith('2026-02-01')
    assert health['soh_limit_reached'] and health['cycle_limit_reached']
