import json
from sqlalchemy import select, func
from src import intelligence_schema as s, operational_schema as o
from src.opportunities import simulated_profile, status
from test_registry import generate, first, account


def test_simulation_is_complete_stable_and_does_not_write(client, database):
    generate(database, 3)
    _, unit = first(client)
    before = client.get('/api/v3/vehicles/' + unit['id'] + '/battery-dossier').json()
    with database.connect() as c:
        vehicle = dict(c.execute(select(s.vehicle_asset).where(s.vehicle_asset.c.id == unit['id'])).mappings().one())
        model = dict(c.execute(select(o.model).where(o.model.c.id == unit['current_model_id'])).mappings().one())
    a = simulated_profile(vehicle, model, [('PR', 'Curitiba')])
    b = simulated_profile(vehicle, model, [('PR', 'Curitiba')])
    assert a == b
    assert len(a['passport']['values']) == 71
    assert a['passport']['counts']['pending'] == 0
    assert a['location_simulated']
    with database.connect() as c:
        assert c.execute(select(func.count()).select_from(s.battery_asset)).scalar_one() == 0
    assert client.get('/api/v3/vehicles/' + unit['id'] + '/battery-dossier').json() == before


def test_health_status_uses_limit_and_data_freshness():
    assert status(79, 80)['status'] == 'priority'
    assert status(83, 80)['status'] == 'near'
    assert status(90, 80)['status'] == 'monitor'
    assert status(None, 80)['status'] == 'insufficient'
    assert status(78, 80, latest_at='2020-01-01')['status'] == 'stale'


def test_mode_switch_is_reversible_for_multiple_months(client, database):
    generate(database, 2, 'jan', '2026-01')
    generate(database, 3, 'feb', '2026-02')
    headers=account(client)
    before=client.get('/api/v3/opportunities?reference=2026-01').json()
    assert before['mode']=='real' and before['total']==0
    changed=client.put('/api/v3/admin/opportunities/settings',json={'mode':'simulated'},headers=headers)
    assert changed.status_code==200,changed.text
    first_month=client.get('/api/v3/opportunities?reference=2026-01').json()
    second_month=client.get('/api/v3/opportunities?reference=2026-02').json()
    assert first_month['total']==2 and second_month['total']==3
    detail=client.get('/api/v3/opportunities/simulated/'+first_month['items'][0]['id']+'/passport').json()
    assert detail['passport']['counts']['total']==71
    assert client.put('/api/v3/admin/opportunities/settings',json={'mode':'real'},headers=headers).status_code==200
    assert client.get('/api/v3/opportunities?reference=2026-01').json()==before


def test_partner_import_preview_and_idempotency(client, database, monkeypatch):
    generate(database, 1)
    _, unit = first(client)
    monkeypatch.setenv('I9_ROLE_TOKENS', json.dumps([{'name':'partner-test','role':'data_engineer','key':'safe-test-token'}]))
    headers = {'X-API-Key':'safe-test-token'}
    body = {'source_url':'https://example.org/battery-report', 'source_record_id':'report-1',
            'vehicle_code':unit['public_identifier'], 'vin':'1HGBH41JXMN109186',
            'state':'PR','municipality':'Curitiba','battery_manufacturer':'Example Cells',
            'battery_serial':'CELL-001','installed_at':'2026-01-01',
            'passport':{'12':{'value':'LFP','status':'confirmed','source':'https://example.org/battery-report'}},
            'measurements':[{'observed_at':'2026-09-01T12:00:00Z','soh_percent':79,'cycle_count':800}]}
    preview = client.post('/api/v3/battery-import/validate',json=body,headers=headers)
    assert preview.status_code == 200,preview.text
    with database.connect() as c:assert c.execute(select(func.count()).select_from(s.battery_asset)).scalar_one()==0
    first_result = client.post('/api/v3/battery-import/records',json=body,headers=headers)
    assert first_result.status_code == 200,first_result.text
    again = client.post('/api/v3/battery-import/records',json=body,headers=headers)
    assert again.status_code == 200 and again.json() == first_result.json()
    with database.connect() as c:
        assert c.execute(select(func.count()).select_from(s.battery_asset)).scalar_one()==1
        assert c.execute(select(func.count()).select_from(s.lifecycle)).scalar_one()==1
    ranked=client.get('/api/v3/opportunities').json()
    assert ranked['items'][0]['status']=='priority'
