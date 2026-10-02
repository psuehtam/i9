"""Airflow 3 DAG: calls the same protected API used by the dashboard.

Daily detection is intentional: publishes each monthly reference once, even if
the upstream file is released after the first monthly check.
"""
from datetime import datetime,timedelta,timezone
from airflow.sdk import dag,task

@dag(dag_id='i9_monthly_fleet',schedule='0 5 * * *',start_date=datetime(2026,9,1,tzinfo=timezone.utc),
     catchup=False,max_active_runs=1,default_args={'retries':2,'retry_delay':timedelta(minutes=10)},tags=['i9','BEV'])
def monthly():
    @task(execution_timeout=timedelta(hours=2))
    def refresh():
        import json,os,time,urllib.request
        base=os.environ['I9_API_URL'].rstrip('/')
        headers={'Content-Type':'application/json','X-Admin-Key':os.environ['I9_ADMIN_API_KEY']}
        req=urllib.request.Request(base+'/api/v1/admin/etl/run',data=b'{}',headers=headers,method='POST')
        with urllib.request.urlopen(req,timeout=30) as response:run_id=json.load(response)['run_id']
        for _ in range(720):
            time.sleep(10)
            with urllib.request.urlopen(base+'/api/v1/etl/runs/'+run_id,timeout=60) as response:run=json.load(response)
            if run and run['status'] in ('SUCESSO','SEM_NOVIDADE'):return run['status']
            if run and run['status']=='ERRO':raise RuntimeError(run['error'])
        raise TimeoutError('ETL não terminou em duas horas')
    refresh()

monthly()
