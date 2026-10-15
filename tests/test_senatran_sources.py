import httpx
import pytest
from fastapi import HTTPException
from src import pipeline as p, senatran_months as months


PAGE = '''<p><strong>Frota Nacional (Janeiro de 2026)</strong></p>
<p><a href="/Frota_por_uf_e_tipo_de_veiculo_Janeiro_2026.xlsx">Frota por UF e Tipo de Veículo</a></p>
<p>07 - <a href="https://dados.transportes.gov.br/dataset/registro-nacional-de-veiculos-automotores-renavam">Quantidade por MunicÃ­pio Marca e Modelo</a>
<a href="/G_TIPO_ESPECIE_EIXOS_Janeiro_2026.xlsx">Tipo, espÃ©cie e eixos</a></p>'''


def mock_sources(monkeypatch, catalog_ok=False, page_ok=True):
    calls = []
    real_client = httpx.Client
    def handle(request):
        calls.append(str(request.url))
        if request.url.host == 'dados.transportes.gov.br':
            if not catalog_ok:
                return httpx.Response(503)
            return httpx.Response(200, json={'success': True, 'result': {'resources': [
                {'name': 'MARCA MODELO', 'description': '2026-01', 'url': 'https://dados.transportes.gov.br/janeiro_2026.zip'}]}})
        assert '/frota-de-veiculos-' in request.url.path, 'Discovery must never download a report'
        return httpx.Response(200 if page_ok else 503, text=PAGE)
    monkeypatch.setattr(p.httpx, 'Client', lambda **kwargs: real_client(transport=httpx.MockTransport(handle), **kwargs))
    return calls


def test_official_page_lists_months_when_api_is_down(database, monkeypatch):
    calls = mock_sources(monkeypatch)
    months.refresh_catalog()
    result = months.months()
    assert len(calls) == 2
    assert result['source_warning'] and not result['last_error']
    item = result['items'][0]
    assert item['reference'] == '2026-01'
    primary, complement = item['datasets']
    assert primary['published'] and not primary['available']
    assert primary['publication_url'].startswith('https://www.gov.br/')
    assert complement['available']
    assert len(item['reports']) == 1
    assert item['reports'][0]['available']
    monkeypatch.setenv('ALLOW_SOURCE_DOWNLOAD', 'true')
    with pytest.raises(HTTPException) as error:
        months.request_import('2026-01', False, 'blocked', dataset='primary')
    assert error.value.status_code == 409
    assert not p.list_jobs()


def test_recovered_api_resolves_file_without_ambiguity(database, monkeypatch):
    mock_sources(monkeypatch, catalog_ok=True)
    months.refresh_catalog()
    primary = months.months()['items'][0]['datasets'][0]
    assert primary['available'] and not primary['ambiguous']


def test_partial_outage_preserves_existing_file_catalog(database, monkeypatch):
    months.refresh_catalog([{'name': 'MARCA MODELO', 'description': '2026-01',
        'url': 'https://dados.transportes.gov.br/janeiro_2026.zip'}])
    mock_sources(monkeypatch)
    months.refresh_catalog()
    assert months.months()['items'][0]['datasets'][0]['available']


def test_both_sources_down_preserves_previous_catalog(database, monkeypatch):
    months.refresh_catalog([{'name': 'MARCA MODELO', 'description': '2026-01',
        'url': 'https://dados.transportes.gov.br/janeiro_2026.zip'}])
    previous = months.months()
    mock_sources(monkeypatch, page_ok=False)
    with pytest.raises(httpx.HTTPStatusError):
        months.refresh_catalog()
    assert months.months()['items'] == previous['items']
    assert months.months()['checked_at'] == previous['checked_at']
