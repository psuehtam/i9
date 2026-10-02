"""Read real data over HTTP and verify public/restricted boundaries without demo identities."""
import json
import os
import time
from src.db import ROOT
import httpx

def main():
    results=[]
    with httpx.Client(base_url='http://127.0.0.1:8000',timeout=90) as c:
        def get(path,expected=200,headers=None):
            start=time.perf_counter();r=c.get(path,headers=headers);assert r.status_code==expected,(path,r.status_code,r.text[:300]);results.append({'path':path,'status':r.status_code,'seconds':round(time.perf_counter()-start,3)});return r.json()
        market=get('/api/v2/market')
        assert market['senatran']['quantity']>0
        if market['senatran']['reference_period']=='2026-07':
            assert market['senatran']['quantity']==222373
        assert market['abve']['quantity']==950183
        assert market['reconciliation']['comparable'] is False and market['reconciliation']['delta'] is None
        assert 'não somar' in (market.get('note') or '').lower() or 'Não somar' in (market.get('note') or '') or 'não' in (market.get('note') or '').lower()
        buses=get('/api/v2/observations?vehicle_category=bus&limit=100')
        assert buses['quantity']==589 and len(buses['items'])==12
        brasilia=next(r for r in buses['items'] if r['municipality']=='Brasília')
        assert brasilia['quantity']==90 and brasilia['model_year'] is None and brasilia['manufacturer'] is None
        bm=get('/api/v2/registry/battery-models?limit=10');assert bm['total']>=608
        get('/api/v2/registry/vehicles',401)
        get('/api/v2/registry/battery-assets',401)
        get('/api/v2/admin/sources',401)
        h={'X-Admin-Key':os.environ['ADMIN_API_KEY']}
        get('/api/v2/session',headers=h)
        get('/api/v2/registry/vehicles',headers=h)
        get('/api/v2/contracts',headers=h)
        src=market['senatran']['id']
        change=get('/api/v2/sources/'+src+'/changelog');assert change['delta']==16557
        scenario=get('/api/v2/opportunities?source_snapshot_id='+src+'&start_year=2026&end_year=2050')
        assert scenario['missing_year_vehicles']>=0
        assert 'by_powertrain' in scenario
        energy=sum(r['potential_mwh'] for r in scenario['items'])
        assert energy>=0
        r=c.post('/api/v2/forecast/battery-availability',json={'vehicle_year':2026});r.raise_for_status();assert r.json()['most_likely_year']==2036
        get('/api/v1/summary?reference=2026-07')
    report={'checked_at':time.strftime('%Y-%m-%dT%H:%M:%S'),'requests':results,'fleet_july':market['senatran']['quantity'] if market['senatran']['reference_period']=='2026-07' else None,'abve_cumulative_august':950183,'bus_registrations_h1':589,'known_nominal_mwh':energy,'note':'ABVE permanece mercado. Energia por propulsão; snapshots publicados não são reescritos. Sem identidades físicas inventadas.'}
    (ROOT/'docs/intelligence-live-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'{len(results)} GETs verificados, cenário POST validado; quantidades e isolamento conferidos.')

if __name__=='__main__':main()
