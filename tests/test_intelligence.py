import pytest
from sqlalchemy import select,func
from src import db,intelligence_schema as s,intelligence as service
from src.intelligence_models import Forecast

@pytest.fixture(autouse=True)
def isolated_raw(monkeypatch,tmp_path):
    monkeypatch.setattr(db,'ROOT',tmp_path)

@pytest.fixture
def auth(monkeypatch):
    monkeypatch.setenv('ADMIN_API_KEY','test-intelligence-secret')
    return {'X-Admin-Key':'test-intelligence-secret'}

def source(client,auth,restricted=False,**kwargs):
    body=dict(provider='TEST',dataset_name='Frota de teste',reference_period='2026-07',source_url='https://example.org/test',license_or_terms='Test only',scope='Coorte teste',metric='individual' if restricted else 'fleet_stock',access_level='restricted' if restricted else 'public',**kwargs)
    r=client.post('/api/v2/sources',json=body,headers=auth);assert r.status_code==201,r.text
    return r.json()['id']

def create(client,auth,entity,body):
    r=client.post('/api/v2/registry/'+entity,json=body,headers=auth)
    assert r.status_code==201,r.text
    return r.json()['id']

def test_migration_preserves_aggregates(client,populate):
    populate();service.migrate();service.migrate()
    with db.engine.connect() as c:
        assert c.execute(select(func.sum(s.aggregate.c.quantity))).scalar()==150
        assert c.execute(select(func.count()).select_from(s.vehicle_asset)).scalar()==0
    r=client.get('/api/v2/market');assert r.status_code==200
    assert r.json()['senatran']['quantity']==150

def test_import_idempotency_and_no_fake_ids(client,auth):
    body={'source':{'provider':'ABVE','dataset_name':'Ônibus','reference_period':'2026-H1','source_url':'https://example.org/bus','license_or_terms':'test only','scope':'Municípios não sobrepostos','metric':'registrations'},'observations':[{'source_record_reference':'DF','quantity':90,'vehicle_category':'bus','state':'DF','municipality':'Brasília'}]}
    a=client.post('/api/v2/imports/aggregates',json=body,headers=auth);assert a.status_code==200,a.text
    assert client.post('/api/v2/imports/aggregates',json=body,headers=auth).json()['inserted']==0
    oid=client.get('/api/v2/observations').json()['items'][0]['id']
    assert client.post(f'/api/v2/observations/{oid}/materialize',json={'count':91},headers=auth).status_code==409
    r=client.post(f'/api/v2/observations/{oid}/materialize',json={'count':90},headers=auth);assert r.status_code==200,r.text
    assert client.get('/api/v2/registry/vehicles').status_code==401
    rows=client.get('/api/v2/registry/vehicles?limit=100',headers=auth).json()['items']
    assert len(rows)==90 and all(x['vin'] is None and x['identity_status']=='aggregate_derived' for x in rows)
    assert client.get('/api/v2/observations').json()['quantity']==90

def test_private_source_not_public_and_duplicate_identity(client,auth):
    sid=source(client,auth,True)
    assert not any(x['id']==sid for x in client.get('/api/v2/sources').json())
    body={'source_snapshot_id':sid,'vin':'9BWZZZ377VT004251','identity_status':'identified'}
    create(client,auth,'vehicles',body)
    assert client.post('/api/v2/registry/vehicles',json=body,headers=auth).status_code==409
    assert client.post('/api/v2/vehicles/lookup',json={'identifier':body['vin']}).status_code==401
    assert len(client.post('/api/v2/vehicles/lookup',json={'identifier':body['vin']},headers=auth).json())==1

def test_installation_history_and_lifecycle(client,auth):
    sid=source(client,auth,True)
    v=create(client,auth,'vehicles',{'source_snapshot_id':sid})
    b=create(client,auth,'battery-assets',{'source_snapshot_id':sid})
    installation={'source_snapshot_id':sid,'vehicle_id':v,'battery_id':b,'installed_at':'2026-01-01'}
    i=create(client,auth,'installations',installation)
    assert client.post('/api/v2/registry/installations',json=installation,headers=auth).status_code==409
    assert client.post(f'/api/v2/installations/{i}/remove',json={'removed_at':'2026-05-01','source_snapshot_id':sid},headers=auth).status_code==200
    create(client,auth,'installations',{**installation,'installed_at':'2026-05-01'})
    event={'battery_id':b,'source_snapshot_id':sid,'observed_at':'2026-06-01T10:00:00Z','event_type':'measurement','soh_percent':95,'cycle_count':100}
    create(client,auth,'lifecycle',event)
    assert client.post('/api/v2/registry/lifecycle',json={**event,'observed_at':'2026-07-01T10:00:00Z','cycle_count':90},headers=auth).status_code==422
    assert client.post('/api/v2/registry/lifecycle',json={**event,'soh_percent':120},headers=auth).status_code==422
    detail=client.get('/api/v2/registry/battery-assets/'+b,headers=auth).json()
    assert detail['record']['soh_percent']==95
    assert len(detail['installations'])==2

def test_forecast_is_explicit_scenario(client):
    r=client.post('/api/v2/forecast/battery-availability',json={'vehicle_year':2022}).json()
    assert [r[k] for k in ('earliest_year','most_likely_year','latest_year')]==[2030,2032,2034]
    assert r['confidence']=='low'
    assert client.post('/api/v2/forecast/battery-availability',json={}).json()['most_likely_year'] is None
    assert client.post('/api/v2/forecast/battery-availability',json={'earliest_age':12,'latest_age':8}).status_code==422

def test_abve_cannot_register_as_fleet_stock(client,auth):
    body=dict(provider='ABVE',dataset_name='BI interno',reference_period='2026-08',source_url='https://example.org/abve',license_or_terms='licensed export',scope='Mercado leve',metric='fleet_stock')
    assert client.post('/api/v2/sources',json=body,headers=auth).status_code==422
    imported={'source':{**body,'metric':'registrations'},'observations':[{'source_record_reference':'BR','quantity':10,'vehicle_category':'light','powertrain_type':'BEV'}]}
    assert client.post('/api/v2/imports/aggregates',json=imported,headers=auth).status_code==200
    imported['source']['metric']='fleet_stock'
    imported['source']['dataset_name']='Tentativa estoque'
    assert client.post('/api/v2/imports/aggregates',json=imported,headers=auth).status_code==422

def test_reconciliation_blocks_false_difference():
    a={'reference_period':'2026-07','scope':'BEV','metric':'fleet_stock','quantity':100,'dataset_name':'fleet'}
    b={**a,'reference_period':'2026-08','quantity':999}
    assert service.reconciliation(a,b)['delta'] is None

def test_opportunity_counts_missing_year_and_unknown_energy():
    rows=[{'model_year':2020,'quantity':10,'state':'PR','municipality':'Curitiba','battery_model_id':'x'},{'model_year':None,'quantity':5}]
    r=service.opportunity(rows,{},2028,2032)
    assert r['missing_year_vehicles']==5
    assert r['items'][0]['known_battery_vehicles']==0
    assert r['items'][0]['recoverable_scenario_mwh'] is None
    assert r['items'][0]['powertrain_type']=='UNKNOWN'
    assert r['by_powertrain']

def test_nonadmin_cannot_accept_evidence(client,auth,monkeypatch):
    monkeypatch.setenv('I9_ROLE_TOKENS','[{"key":"engineer-key","role":"data_engineer","name":"engineer"}]')
    sid=source(client,auth)
    spec=create(client,auth,'vehicle-specs',{'source_snapshot_id':sid,'manufacturer':'Example','model':'Bus'})
    bm=create(client,auth,'battery-models',{'source_snapshot_id':sid})
    body={'source_snapshot_id':sid,'vehicle_spec_id':spec,'battery_model_id':bm,'status':'accepted','notes':'Reviewed example only','evidence_type':'oem'}
    assert client.post('/api/v2/registry/evidence',json=body,headers={'X-API-Key':'engineer-key'}).status_code==403

def test_no_unknown_fields_in_aggregate(client,auth):
    body={'source':{'provider':'TEST','dataset_name':'test','reference_period':'2026-07','source_url':'https://example.org','license_or_terms':'test','scope':'scope test','metric':'fleet_stock'},'observations':[{'quantity':1,'source_record_reference':'1','vin':'private-identifier'}]}
    assert client.post('/api/v2/imports/aggregates',json=body,headers=auth).status_code==422

def test_tabular_import_validates_and_retains_raw(client,auth):
    import base64
    sid=source(client,auth)
    body={'source_snapshot_id':sid,'format':'csv','content_base64':base64.b64encode(b'source_record_reference;quantity;powertrain_type\nrow1;20;PHEV\n').decode()}
    r=client.post('/api/v2/imports/tabular',json=body,headers=auth);assert r.status_code==200,r.text
    assert client.post('/api/v2/imports/tabular',json=body,headers=auth).json()['inserted']==0
    assert client.get('/api/v2/observations?powertrain_type=PHEV').json()['quantity']==20
    body['content_base64']=base64.b64encode(b'vin;quantity\nPRIVATE;10').decode()
    assert client.post('/api/v2/imports/tabular',json=body,headers=auth).status_code==422

def test_published_review_does_not_rewrite_source(client,auth,populate):
    populate();service.migrate()
    parent=client.get('/api/v2/market').json()['senatran']['id']
    sid=source(client,auth)
    spec=create(client,auth,'vehicle-specs',{'source_snapshot_id':sid,'manufacturer':'BYD','model':'Dolphin','trim':'PLUS','model_year_start':2024,'model_year_end':2024,'powertrain':'BEV'})
    bm=create(client,auth,'battery-models',{'source_snapshot_id':sid,'nominal_capacity_kwh':60,'confidence':'high'})
    eid=create(client,auth,'evidence',{'source_snapshot_id':sid,'vehicle_spec_id':spec,'battery_model_id':bm,'confidence':'high','status':'accepted','evidence_type':'oem','notes':'Test evidence with exact variant only'})
    before=client.get('/api/v2/observations',params={'source_snapshot_id':parent}).json()
    r=client.post(f'/api/v2/evidence/{eid}/publish',json={'source_snapshot_id':parent},headers=auth);assert r.status_code==200,r.text
    derived=client.get('/api/v2/observations',params={'source_snapshot_id':r.json()['id']}).json()
    assert derived['quantity']==before['quantity']==150
    after=client.get('/api/v2/observations',params={'source_snapshot_id':parent}).json()
    assert after==before
    assert any(x['battery_model_id']==bm for x in derived['items'])

def test_identity_resolution_preserves_known_fields(client,auth):
    sid=source(client,auth,True)
    vid=create(client,auth,'vehicles',{'source_snapshot_id':sid,'manufacturer':'Known make','model':'Known model'})
    r=client.post(f'/api/v2/vehicles/{vid}/identify',json={'source_snapshot_id':sid,'vin':'9BWZZZ377VT004251','identity_status':'identified'},headers=auth)
    assert r.status_code==200
    assert client.get('/api/v2/registry/vehicles/'+vid,headers=auth).json()['record']['manufacturer']=='Known make'

def test_private_evidence_not_exposed_in_public_model_detail(client,auth):
    public=source(client,auth);private=source(client,auth,True)
    spec=create(client,auth,'vehicle-specs',{'source_snapshot_id':public,'manufacturer':'M','model':'X'})
    bm=create(client,auth,'battery-models',{'source_snapshot_id':public})
    create(client,auth,'evidence',{'source_snapshot_id':private,'vehicle_spec_id':spec,'battery_model_id':bm,'evidence_type':'partner','notes':'Private technical partner note'})
    assert client.get('/api/v2/registry/battery-models/'+bm).json()['evidence']==[]

def test_daily_scheduler_persistent_claim(client,monkeypatch):
    from datetime import datetime
    from src import scheduler,etl
    calls=[]
    monkeypatch.setattr(etl,'run_monthly',lambda: calls.append(1) or {'status':'SEM_NOVIDADE'})
    morning=datetime(2026,9,14,9,tzinfo=scheduler.BRASILIA)
    assert scheduler.tick(morning)['status']=='SEM_NOVIDADE'
    assert scheduler.tick(morning)['status']=='already_checked'
    assert len(calls)==1
    assert scheduler.tick(morning.replace(day=15,hour=1))['status']=='not_due'

def test_bus_can_have_multiple_packs_but_pack_cannot_be_in_two_vehicles(client,auth):
    sid=source(client,auth,True)
    v=create(client,auth,'vehicles',{'source_snapshot_id':sid,'vehicle_category':'bus'})
    other=create(client,auth,'vehicles',{'source_snapshot_id':sid,'vehicle_category':'bus'})
    b1=create(client,auth,'battery-assets',{'source_snapshot_id':sid})
    b2=create(client,auth,'battery-assets',{'source_snapshot_id':sid})
    base={'source_snapshot_id':sid,'vehicle_id':v,'installed_at':'2026-01-01'}
    create(client,auth,'installations',{**base,'battery_id':b1,'position':'roof-1'})
    create(client,auth,'installations',{**base,'battery_id':b2,'position':'roof-2'})
    assert client.post('/api/v2/registry/installations',json={**base,'vehicle_id':other,'battery_id':b1,'position':'rear-1'},headers=auth).status_code==409


def test_battery_passport_and_vehicle_navigation(client,auth):
    sid=source(client,auth,True)
    vehicle=create(client,auth,'vehicles',{'source_snapshot_id':sid})
    battery=create(client,auth,'battery-assets',{'source_snapshot_id':sid,'battery_identifier':'PACK-001'})
    create(client,auth,'installations',{'source_snapshot_id':sid,'vehicle_id':vehicle,'battery_id':battery,'installed_at':'2026-01-01'})
    path='/api/v2/battery-assets/'+battery+'/passport'
    assert client.post(path,json={'values':{'3':'Fabricante'} }).status_code==401
    assert client.post(path,json={'values':{'72':'inválido'}},headers=auth).status_code==422
    assert client.post(path,json={'values':{'3':'Fabricante','68':'0'}},headers=auth).status_code==200
    passport=client.get('/api/v2/registry/battery-assets/'+battery,headers=auth).json()['passport']
    assert len(passport['fields'])==71 and passport['values']['1']=='PACK-001'
    assert passport['values']['68']=='0' and passport['filled']==4
    client.post(path,json={'values':{'3':None}},headers=auth)
    passport=client.get('/api/v2/registry/battery-assets/'+battery,headers=auth).json()['passport']
    assert passport['values']['3'] is None and passport['values']['68']=='0'
    linked=client.get('/api/v2/registry/vehicles/'+vehicle,headers=auth).json()['installations']
    assert linked[0]['battery']['id']==battery


def test_passport_tracks_new_measurements(client,auth):
    sid=source(client,auth,True)
    battery=create(client,auth,'battery-assets',{'source_snapshot_id':sid})
    path='/api/v2/battery-assets/'+battery+'/passport'
    assert client.post(path,json={'values':{'62':'90','68':'10','3':'Fabricante'}},headers=auth).status_code==200
    event={'battery_id':battery,'source_snapshot_id':sid,'event_type':'measurement','observed_at':'2026-06-01T10:00:00Z','soh_percent':85,'cycle_count':20}
    create(client,auth,'lifecycle',event)
    passport=client.get('/api/v2/registry/battery-assets/'+battery,headers=auth).json()['passport']
    assert passport['values']['62']=='85.0' and passport['values']['68']=='20'
    assert passport['values']['3']=='Fabricante'
    assert client.post(path,json={'values':{'62':'100'}},headers=auth).status_code==422
    create(client,auth,'lifecycle',{**event,'observed_at':'2026-07-01T10:00:00Z','soh_percent':80,'cycle_count':30})
    passport=client.get('/api/v2/registry/battery-assets/'+battery,headers=auth).json()['passport']
    assert passport['values']['62']=='80.0' and passport['values']['68']=='30'


def test_guided_registration_atomic_and_optional_battery(client,auth):
    sid=source(client,auth,True)
    path='/api/v2/vehicles/register-guided'
    body={'vehicle':{'source_snapshot_id':sid,'manufacturer':'Teste','model':'EV'},'battery':{'source_snapshot_id':sid},'installed_at':'2026-01-01'}
    assert client.post(path,json=body).status_code==401
    result=client.post(path,json=body,headers=auth)
    assert result.status_code==201,result.text
    detail=client.get('/api/v2/registry/vehicles/'+result.json()['id'],headers=auth).json()
    assert detail['installations'][0]['battery']['id']==result.json()['battery_id']
    assert detail['installations'][0]['battery']['manufacturer_serial_number'] is None
    rejected=client.post(path,json={'vehicle':{'source_snapshot_id':sid},'battery_id':result.json()['battery_id'],'installed_at':'2026-02-01'},headers=auth)
    assert rejected.status_code==409
    assert client.get('/api/v2/registry/vehicles',headers=auth).json()['total']==1
    skipped=client.post(path,json={'vehicle':{'source_snapshot_id':sid}},headers=auth)
    assert skipped.status_code==201 and skipped.json()['battery_id'] is None
    assert client.post(path,json={**body,'installed_at':None},headers=auth).status_code==422


def test_guided_registration_duplicate_rolls_back_new_battery(client,auth):
    sid=source(client,auth,True)
    create(client,auth,'vehicles',{'source_snapshot_id':sid,'plate':'ABC1D23','identity_status':'identified'})
    body={'vehicle':{'source_snapshot_id':sid,'plate':'ABC1D23','identity_status':'identified'},'battery':{'source_snapshot_id':sid,'passport_identifier':'NEW-PACK'},'installed_at':'2026-01-01'}
    result=client.post('/api/v2/vehicles/register-guided',json=body,headers=auth)
    assert result.status_code==409
    assert client.get('/api/v2/registry/battery-assets',headers=auth).json()['total']==0


def test_guided_registration_existing_removed_battery(client,auth):
    sid=source(client,auth,True)
    vehicle=create(client,auth,'vehicles',{'source_snapshot_id':sid})
    battery=create(client,auth,'battery-assets',{'source_snapshot_id':sid})
    create(client,auth,'installations',{'source_snapshot_id':sid,'vehicle_id':vehicle,'battery_id':battery,'installed_at':'2026-01-01','removed_at':'2026-02-01'})
    result=client.post('/api/v2/vehicles/register-guided',json={'vehicle':{'source_snapshot_id':sid},'battery_id':battery,'installed_at':'2026-02-01'},headers=auth)
    assert result.status_code==201,result.text
    public_source=source(client,auth)
    assert client.post('/api/v2/vehicles/register-guided',json={'vehicle':{'source_snapshot_id':public_source}},headers=auth).status_code==422


def test_unified_search_private_literal_and_pending(client,auth):
    sid=source(client,auth,True)
    vehicle=create(client,auth,'vehicles',{'source_snapshot_id':sid,'manufacturer':'Busca','model':'Teste EV','plate':'XYZ1A23','identity_status':'identified'})
    battery=create(client,auth,'battery-assets',{'source_snapshot_id':sid,'battery_identifier':'BUSCA-PACK'})
    search='/api/v2/records/search'
    assert client.post(search,json={'term':'Busca'}).status_code==401
    results=client.post(search,json={'term':'Busca'},headers=auth).json()
    assert {r['kind'] for r in results['items']}=={'vehicles','battery-assets'}
    found=client.post(search,json={'term':'xyz1a23'},headers=auth).json()['items']
    assert found[0]['record']['id']==vehicle
    assert found[0]['pending']==[{'code':'installation','label':'Sem bateria vinculada'}]
    assert client.post(search,json={'term':'%'},headers=auth).json()['total']==0
    assert client.post(search,json={'term':'   '},headers=auth).status_code==422
    create(client,auth,'installations',{'source_snapshot_id':sid,'vehicle_id':vehicle,'battery_id':battery,'installed_at':'2026-01-01'})
    record=client.get('/api/v2/registry/vehicles/'+vehicle,headers=auth).json()
    assert record['pending']==[]
    assert len(record['installations'])==1
    pending=client.get('/api/v2/registry/battery-assets/'+battery,headers=auth).json()['pending']
    assert any(p['code']=='passport' for p in pending)
    with db.engine.connect() as c:
        audits=c.execute(select(s.audit).where(s.audit.c.action=='search')).mappings().all()
        assert audits and all('term' not in r['details'] for r in audits)


def test_pending_identity_and_missing_battery_code(client,auth):
    sid=source(client,auth,True)
    vehicle=create(client,auth,'vehicles',{'source_snapshot_id':sid})
    battery=create(client,auth,'battery-assets',{'source_snapshot_id':sid})
    vehicles=client.get('/api/v2/registry/vehicles',headers=auth).json()['items']
    assert vehicles[0]['id']==vehicle
    assert {p['code'] for p in vehicles[0]['pending']}=={'identity','installation'}
    detail=client.get('/api/v2/registry/battery-assets/'+battery,headers=auth).json()
    assert {p['code'] for p in detail['pending']}=={'identifier','passport'}
    path='/api/v2/battery-assets/'+battery+'/identity'
    assert client.post(path,json={'source_snapshot_id':sid,'battery_identifier':'CODE-123'}).status_code==401
    assert client.post(path,json={'source_snapshot_id':sid,'battery_identifier':'CODE-123'},headers=auth).status_code==200
    detail=client.get('/api/v2/registry/battery-assets/'+battery,headers=auth).json()
    assert all(p['code']!='identifier' for p in detail['pending'])
    assert detail['passport']['values']['1']=='CODE-123'
    result=client.post('/api/v2/records/search',json={'term':'CODE-123'},headers=auth).json()
    assert result['items'][0]['record']['id']==battery

import pytest

@pytest.fixture(autouse=True)
def legacy_contract_mode(monkeypatch):
    monkeypatch.setenv('I9_LEGACY_WRITES','true')
