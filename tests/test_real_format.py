import pytest
from src.transform.ingest import parse_quantity,UF_NAMES

@pytest.mark.parametrize('value,result',[(' 6.0',6),('123.00',123),('0.0',0),('100',100)])
def test_official_quantity_representation(value,result):assert parse_quantity(value)==result

@pytest.mark.parametrize('value',['1.5','-1.0','NaN','inf','1e3','1,5'])
def test_never_truncate_fractional_vehicles(value):
    with pytest.raises(ValueError):parse_quantity(value)

def test_actual_senatran_header_and_state_name(populate):
    result=populate(text='UF;Município;Marca Modelo;Ano Fabricação Veículo CRV;Qtd. Veículos\nPARANA;CURITIBA;I/BYD DOLPHIN GS;2026; 6.0\n')
    assert result['vehicles']==6

def test_state_map_is_complete():
    assert len(UF_NAMES)==27 and len(set(UF_NAMES.values()))==27

def test_missing_year_counts_as_fleet_not_forecast(client,populate):
    populate(text='UF;Município;Marca Modelo;Ano Fabricação Veículo CRV;Qtd. Veículos\nPARANA;CURITIBA;I/BYD DOLPHIN GS;Sem Informação; 6.0\n')
    assert client.get('/api/v1/summary').json()['vehicles']==6
    f=client.get('/api/v1/forecast?scenario=8').json()
    assert f['items']==[] and f['missing_year_vehicles']==6
    assert client.get('/api/v1/fleet').json()['items'][0]['vehicle_year'] is None

def test_unknown_location_is_not_assigned_to_a_state(client,populate,database):
    from sqlalchemy import insert
    from src.db import locations
    with database.begin() as c:c.execute(insert(locations).values(id='unknown',uf=None,city='Não informado',normalized='SEM INFORMACAO'))
    populate(text='UF;Município;Marca Modelo;Ano Fabricação Veículo CRV;Qtd. Veículos\nSem Informação;Sem Informação;I/BYD DOLPHIN GS;Sem Informação; 6.0\n')
    assert client.get('/api/v1/summary').json()['vehicles']==6
    assert client.get('/api/v1/summary?uf=PR').json()['vehicles']==0
    assert client.get('/api/v1/data-quality').json()['missing_location_vehicles']==6

def test_reviewed_locality_alias(populate,database):
    from sqlalchemy import insert
    from src.db import locations
    with database.begin() as c:c.execute(insert(locations).values(id='4119251',uf='PR',city='Pinhal de São Bento',normalized='PINHAL DE SAO BENTO'))
    result=populate(text='UF;Município;Marca Modelo;Ano Fabricação Veículo CRV;Qtd. Veículos\nPARANA;PINHAL DO SAO BENTO;I/BYD DOLPHIN GS;2026; 6.0\n')
    assert result['vehicles']==6
