import pytest
from sqlalchemy import create_engine, insert
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from src import db,catalog,etl
from src.api import main
from src.connectors import public
from src.transform import ingest

@pytest.fixture
def database(monkeypatch):
    monkeypatch.setenv('I9_SCHEDULER_ENABLED','false')
    monkeypatch.setenv('I9_ON_DEMAND_WORKER','false')
    monkeypatch.setenv('I9_UPDATES_PAUSED','false')
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    db.meta.create_all(engine)
    for mod in (db,catalog,etl,main,public,ingest):monkeypatch.setattr(mod,'engine',engine)
    catalog.seed_catalog()
    with engine.begin() as c:
        c.execute(insert(db.locations),[dict(id='4106902',uf='PR',city='Curitiba',normalized='CURITIBA'),dict(id='3550308',uf='SP',city='São Paulo',normalized='SAO PAULO')])
    yield engine
    engine.dispose()

@pytest.fixture
def client(database):
    with TestClient(main.app) as c:yield c

@pytest.fixture
def populate(database,tmp_path):
    def load(reference='2026-07',text=None):
        run=etl.start_run(reference)
        path=tmp_path/(reference+'.csv')
        path.write_text(text or 'UF;MUNICIPIO;MARCA MODELO;ANO FABRICACAO;QUANTIDADE\nPR;Curitiba;I/BYD DOLPHIN GS;2026;100\nSP;São Paulo;I/BYD DOLPHIN PLUS;2024;50\nPR;Curitiba;I/TOYOTA COROLLA;2026;999\n',encoding='utf-8')
        return ingest.process_file(path,reference,public.file_hash(path),run)
    return load
