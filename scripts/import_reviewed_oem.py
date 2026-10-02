"""Small OEM catalog expansion: published specifications, never inferred installed packs."""
from sqlalchemy import select,insert,func
from src import db,intelligence_schema as s,pipeline_schema as p
from src import pipeline
from src.intelligence import stable,VERSION
from src.connectors.public import download,now

def main():
    db.init_db()
    configs=[
        dict(key='gwm-h6-phev34-2025',url='https://www.gwmmotors.com.br/content/dam/gwm/pages/br/pt/models/haval-h6-phev-34-2025/FichaTecnica_Haval_H6_PHEV34_2025.pdf',file='gwm-h6-phev34-2025.pdf',make='GWM',model='Haval H6',trim='PHEV34',year=2025,powertrain='PHEV',category='light',capacity=34,chemistry=None,status='accepted',notes='Ficha GWM Haval H6 PHEV34 2025, página 10: 34 kWh. Não extrapolar para PHEV35 2026; fabricante do pack e química não informados.'),
        dict(key='mercedes-eo500u-pack-98',url='https://www.mercedes-benz-trucks.com.br/onibus/eletrico/tecnologia/bateria',file='mercedes-eo500u-bateria.html',make='Mercedes-Benz',model='eO500U',trim=None,year=None,powertrain='BEV',category='bus',capacity=98,chemistry='NMC',status='candidate',notes='Fonte OEM: cada pack possui 98 kWh; configurações de 3 a 6 packs, até 588 kWh. Ano e configuração por ônibus não informados. Não usar 98 kWh como capacidade de todo o veículo nem aplicar aos emplacamentos agregados.')]
    for item in configs:
        path=db.ROOT/'data/raw/oem'/item['file'];digest=download(item['url'],path,max_bytes=20_000_000)
        if item['category']=='bus':
            content=path.read_text(encoding='utf-8')
            if not all(v in content for v in ('98','588','NMC')):raise ValueError('Texto OEM mudou; revisar ficha de ônibus')
        elif not path.read_bytes().startswith(b'%PDF'):raise ValueError('Fonte GWM não retornou PDF')
        sid=stable('oem:'+item['key']);vid=stable('oem-spec:'+item['key']);bid=stable('oem-battery:'+item['key'])
        with db.engine.begin() as c:
            if c.execute(select(s.source_snapshot.c.id).where(s.source_snapshot.c.id==sid)).first():continue
            c.execute(insert(s.source_snapshot).values(id=sid,provider=item['make'],dataset_name=item['model']+' · ficha técnica',reference_period=None,retrieved_at=now(),method='review',raw_file_hash=digest,raw_storage_path=str(path.relative_to(db.ROOT)),source_version='OEM-reviewed-2026-09-14',transformation_version=VERSION,license_or_terms='Especificações públicas do fabricante; consultar termos na origem',ingestion_status='success',record_count=1,source_url=item['url'],scope=item['notes'],metric='technical',access_level='public',metadata={'bytes':path.stat().st_size}))
            c.execute(insert(s.vehicle_spec).values(id=vid,manufacturer=item['make'],model=item['model'],trim=item['trim'],model_year_start=item['year'],model_year_end=item['year'],powertrain=item['powertrain'],country_market='BR',vehicle_category=item['category'],source_snapshot_id=sid))
            c.execute(insert(s.battery_model).values(id=bid,manufacturer=None,model_name=None,chemistry=item['chemistry'],nominal_capacity_kwh=item['capacity'],confidence='high',source_snapshot_id=sid,field_sources={'nominal_capacity_kwh':item['url'],**({'chemistry':item['url']} if item['chemistry'] else {})}))
            c.execute(insert(s.compatibility).values(id=stable('oem-evidence:'+item['key']),vehicle_spec_id=vid,battery_model_id=bid,source_snapshot_id=sid,confidence='high',evidence_type='oem',verified_by='OEM-reviewed-import',verified_at=now(),status=item['status'],notes=item['notes']))
        print(item['make'],item['model'],item['status'])

    # Estes aliases existem nos arquivos 07 preservados. A regra vincula apenas
    # o nome SENATRAN ao modelo comprovado; ela não atribui bateria, placa ou local.
    reviewed_aliases=[
        dict(raw='M BENZ EO500 U2134',manufacturer='Mercedes-Benz',model='eO500U',category='bus',
             subtype='electric_bus_chassis',segment='Ônibus urbano',body='chassi',
             evidence='Ficha oficial Mercedes-Benz eO500U: https://www.mercedes-benz-trucks.com.br/onibus/eletrico/eo500u'),
        dict(raw='BYD D9A 20 410',manufacturer='BYD',model='D9A',category='bus',
             subtype='standard_urban_bus',segment='Ônibus urbano',body='padron',
             evidence='Publicação oficial BYD D9A: https://www.byd.com/br/noticias-byd-brasil/onibus-BYD-entra-em-teste-em-BH'),
    ]
    for item in reviewed_aliases:
        with db.engine.connect() as c:
            version=c.execute(select(func.max(p.rule.c.version)).where(p.rule.c.raw_name==item['raw'])).scalar_one() or 0
            latest=c.execute(select(p.rule.c.decision).where(p.rule.c.raw_name==item['raw']).order_by(p.rule.c.version.desc()).limit(1)).scalar_one_or_none()
        if latest=='include':
            print(item['raw'],'já aprovado')
            continue
        pipeline.approve_rule(item['raw'],'include',item['evidence'],'OEM-reviewed-import',
            item['manufacturer'],item['model'],'BEV',item['category'],item['subtype'],item['segment'],item['body'],version)
        print(item['raw'],'aprovado')

    byd_url='https://www.byd.com/br/noticias-byd-brasil/onibus-BYD-entra-em-teste-em-BH'
    byd_sid=stable('oem:byd-d9a-official');byd_vid=stable('oem-spec:byd-d9a-official')
    with db.engine.begin() as c:
        if not c.execute(select(s.source_snapshot.c.id).where(s.source_snapshot.c.id==byd_sid)).first():
            c.execute(insert(s.source_snapshot).values(id=byd_sid,provider='BYD',dataset_name='D9A · publicação oficial',
                reference_period=None,retrieved_at=now(),method='review',raw_file_hash=stable(byd_url),raw_storage_path=None,
                source_version='OEM-reviewed-2026-09-23',transformation_version=VERSION,
                license_or_terms='Especificações públicas do fabricante; consultar termos na origem',ingestion_status='success',
                record_count=1,source_url=byd_url,scope='D9A elétrico padron; autonomia aproximada de 250 km e capacidade de 78 passageiros.',
                metric='technical',access_level='public',metadata={'reviewed':True}))
            c.execute(insert(s.vehicle_spec).values(id=byd_vid,manufacturer='BYD',model='D9A',trim=None,powertrain='BEV',
                country_market='BR',vehicle_category='bus',vehicle_subtype='standard_urban_bus',segment='Ônibus urbano',body_type='padron',
                passenger_capacity=78,range_km=250,source_snapshot_id=byd_sid,
                field_sources={'passenger_capacity':byd_url,'range_km':byd_url}))
            print('BYD D9A','referência técnica')

if __name__=='__main__':main()
