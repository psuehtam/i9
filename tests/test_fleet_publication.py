from sqlalchemy import insert, select, func, update
from src import intelligence_schema as s
from src import operational_schema as o
from src import fleet_publication as fleet

def source(database, sid, reference, quantity):
    with database.begin() as c:
        c.execute(insert(s.source_snapshot).values(id=sid,provider='SENATRAN',dataset_name='Frota validada',reference_period=reference,retrieved_at=reference+'-28',method='download',raw_file_hash=sid,transformation_version='test',ingestion_status='success',record_count=1,access_level='public',scope='Brasil',metric='fleet_stock'))
        c.execute(insert(s.aggregate).values(id='agg-'+sid,source_snapshot_id=sid,reference_period=reference,country='BR',vehicle_category='light',manufacturer='BYD',model='DOLPHIN',powertrain_type='BEV',quantity=quantity,source_record_reference='1'))

def test_materializes_exact_units_and_public_navigation(client,database,monkeypatch):
    monkeypatch.setenv('ADMIN_API_KEY','secret');source(database,'july','2026-07',90)
    monkeypatch.setenv('I9_MACHINE_KEY_ENABLED','true')
    from src import pipeline
    pipeline.initialize()
    response=client.post('/api/v3/admin/jobs',headers={'X-Admin-Key':'secret'},json={'kind':'materialize','payload':{'source_snapshot_id':'july'},'idempotency_key':'july-generate'})
    assert response.status_code==202
    pipeline.run_once()
    assert pipeline.get_job(response.json()['id'])['status']=='complete'
    models=client.get('/api/v3/models').json();assert models['total']==1 and models['items'][0]['quantity']==90
    group=models['items'][0];page=client.get(f"/api/v3/models/{group['id']}/vehicles?limit=25&offset=75").json()
    assert page['total']==90 and len(page['items'])==15
    assert page['items'][-1]['public_identifier'].endswith('-000090')
    assert all(x['vin'] is None and x['plate'] is None and x['battery_count']==0 for x in page['items'])
    detail=client.get('/api/v3/vehicles/'+page['items'][0]['public_identifier'])
    assert detail.status_code==200 and detail.json()['battery_status']=='Bateria ainda não identificada'

def test_reprocessing_is_idempotent_and_new_month_switches_only_when_complete(client,database,monkeypatch):
    monkeypatch.setenv('ADMIN_API_KEY','secret');source(database,'june','2026-06',4);source(database,'july2','2026-07',6)
    first=fleet.materialize('june',2,True);assert fleet.materialize('june',2,True)['id']==first['id']
    staged=fleet.materialize('july2',2,False);assert staged['materialized_units']==2
    assert client.get('/api/v3/models').json()['publication']['reference_period']=='2026-06'
    finished=fleet.materialize('july2',2,True);assert finished['status']=='complete'
    result=client.get('/api/v3/models').json();assert result['publication']['reference_period']=='2026-07' and result['items'][0]['quantity']==6
    with database.connect() as c:
        assert c.execute(select(func.count()).select_from(s.vehicle_asset)).scalar()==6
        assert c.execute(select(func.count()).select_from(s.fleet_unit_membership).where(s.fleet_unit_membership.c.publication_id==finished['id'])).scalar()==6

def test_failed_publication_keeps_previous_active(database):
    source(database,'old','2026-05',2);old=fleet.materialize('old',10,True);source(database,'new','2026-06',3);new=fleet.prepare('new')
    with database.begin() as c:c.execute(update(s.fleet_publication).where(s.fleet_publication.c.id==new['id']).values(status='failed',error='interrupted'))
    with database.connect() as c:assert fleet.active_publication(c)['id']==old['id']

def test_historical_reprocessing_does_not_expose_extra_units(database):
    source(database,'active-july','2026-07',3)
    active=fleet.materialize('active-july',10,True)
    source(database,'historical-june','2026-06',5)

    historical=fleet.materialize('historical-june',10,True)

    with database.connect() as c:
        assert fleet.active_publication(c)['id']==active['id']
        assert historical['stage']=='historical'
        assert c.execute(select(func.count()).select_from(o.registry).where(o.registry.c.visible.is_(True))).scalar()==3
        assert c.execute(select(func.count()).select_from(o.registry)).scalar()==5

def test_public_reads_but_write_requires_credentials(client,database):
    source(database,'public','2026-08',1);fleet.materialize('public',10,True)
    assert client.get('/api/v3/models').status_code==200
    assert client.post('/api/v3/admin/jobs',json={'kind':'materialize','payload':{'source_snapshot_id':'public'},'idempotency_key':'public'}).status_code==401
