from sqlalchemy import create_engine
from fastapi.testclient import TestClient
from src import db,catalog
from src.api import main

def test_one_connection_pool_can_resolve_default_reference(monkeypatch,tmp_path):
    engine=create_engine(f'sqlite:///{tmp_path / "pool.db"}',connect_args={'check_same_thread':False},pool_size=1,max_overflow=0,pool_timeout=.1)
    for module in (db,catalog,main):monkeypatch.setattr(module,'engine',engine)
    with TestClient(main.app) as c:
        for path in ('summary','fleet','forecast','filters','data-quality'):
            assert c.get('/api/v1/'+path).status_code==200
    engine.dispose()
