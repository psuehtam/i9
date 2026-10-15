import pytest
from openpyxl import Workbook
from src import db, pipeline as p, senatran_months as months, senatran_reports as reports
from test_pipeline_postgres import postgres
from concurrent.futures import ThreadPoolExecutor


RESOURCES = [
    {'name': 'MARCA MODELO', 'description': '2026-01', 'url': 'https://dados.transportes.gov.br/dataset/example', 'published_only': True},
    *[{'name': name, 'description': '2026-01', 'url': f'https://www.gov.br/{name}_2026-01.xlsx', 'report_only': True} for name in ('UF', 'Municipio')],
]


def test_month_imports_all_available_reports_without_primary(database, monkeypatch):
    monkeypatch.setenv('ALLOW_SOURCE_DOWNLOAD', 'true')
    months.refresh_catalog(RESOURCES)
    assert not p.list_jobs()
    first = months.request_import('2026-01', False, 'one')
    assert len(first['job_ids']) == 2
    assert months.request_import('2026-01', False, 'two') == first
    jobs = p.list_jobs()
    assert all(j['kind'] == 'official_report_remote' for j in jobs)
    assert len({j['payload']['report_id'] for j in jobs}) == 2
    assert all(r['job']['status'] == 'queued' for r in months.months()['items'][0]['reports'])


def test_concurrent_month_reports_share_jobs(postgres, monkeypatch):
    monkeypatch.setenv('ALLOW_SOURCE_DOWNLOAD', 'true')
    months.refresh_catalog(RESOURCES)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda key: months.request_import('2026-01', False, key), ['one', 'two']))
    assert results[0] == results[1]
    assert len(results[0]['job_ids']) == 2


def test_workbook_import_is_readable_and_idempotent(client, database, monkeypatch, tmp_path):
    monkeypatch.setattr(db, 'ROOT', tmp_path)
    path = tmp_path / 'report.xlsx'
    workbook = Workbook()
    workbook.active.append(['UF', 'Total'])
    workbook.active.append(['SP', 120])
    workbook.save(path)
    payload = {'reference': '2026-01', 'report_id': 'uf', 'report_name': 'Frota por UF', 'url': 'https://www.gov.br/example.xlsx'}
    p.initialize()
    p.enqueue('official_report_remote', payload, 'test')
    lease = p.claim('test')
    result = reports.import_report(path, payload, lease)
    assert result['rows'] == 2
    assert reports.import_report(path, payload, lease)['source_snapshot_id'] == result['source_snapshot_id']
    assert len(reports.reports()['items']) == 1
    response = client.get(f"/api/v3/senatran/reports/{result['source_snapshot_id']}/rows?offset=1&limit=1")
    assert response.status_code == 200
    assert response.json()['items'][0]['values'] == ['SP', 120]
    assert client.get('/api/v3/senatran/reports').json()['items'][0]['reference'] == '2026-01'
    workbook.active.delete_rows(1, 2)
    workbook.save(path)
    with pytest.raises(p.PermanentError):
        reports.import_report(path, payload, lease)
    assert len(reports.reports()['items']) == 1
    assert reports.report_rows(result['source_snapshot_id'])['total'] == 2


def test_fuel_scope_excludes_combustion_and_paginates(client, database, monkeypatch, tmp_path):
    monkeypatch.setattr(db, 'ROOT', tmp_path)
    path = tmp_path / 'fuel.xlsx'
    workbook = Workbook()
    workbook.active.append(['UF', 'Município', 'Combustível Veículo', 'Qtd. Veículos'])
    for fuel, quantity in [('GASOLINA', 999), ('ELETRICO/FONTE EXTERNA', 10), ('GASOLINA/ELETRICO', 20), ('ELETRICO/FONTE INTERNA', 4), ('HIBRIDO', 5)]:
        workbook.active.append(['SP', 'TESTE', fuel, quantity])
    workbook.save(path)
    payload = {'reference': '2026-09', 'report_id': 'fuel', 'report_name': 'Combustível', 'url': 'https://www.gov.br/fuel.xlsx'}
    p.initialize()
    p.enqueue('official_report_remote', payload, 'fuel')
    result = reports.import_report(path, payload, p.claim('fuel'))
    data = reports.report_rows(result['source_snapshot_id'], 1, 1, 'electrified')
    assert data['total_quantity'] == 39 and data['total'] == 4
    assert data['items'][0]['values'][2] == 'GASOLINA/ELETRICO'
    electric = reports.report_rows(result['source_snapshot_id'], 0, 50, 'electric')
    assert electric['total_quantity'] == 10 and electric['total'] == 1
