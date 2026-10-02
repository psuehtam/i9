"""One-time audited derivation: preserve the original database, correct a
verified alias in a NEW dataset. Never mutate an existing published dataset.
"""
import json,sqlite3,uuid
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def revise():
    original=ROOT/'data/i9.db'
    destination=ROOT/'data/i9-validated-v2.db'
    if destination.exists():raise RuntimeError('Revision already exists; refusing to replace it')
    with sqlite3.connect(original) as source,sqlite3.connect(destination) as target:
        source.backup(target)
        before=target.execute('SELECT reference,SUM(quantity) FROM frota_snapshot GROUP BY reference ORDER BY reference').fetchall()
        model_id='byd-dolphin-gs-2026'
        aliases=json.loads(target.execute('SELECT aliases FROM modelo_veiculo WHERE id=?',(model_id,)).fetchone()[0])
        if 'BYD DOLPHIN GS 180EV' not in aliases:aliases.append('BYD DOLPHIN GS 180EV')
        target.execute('UPDATE modelo_veiculo SET aliases=? WHERE id=?',(json.dumps(aliases),model_id))
        cur=target.execute('UPDATE frota_snapshot SET battery_id=?,confidence=?,match_method=? WHERE raw_name=? AND vehicle_year=?',
            ('byd-dolphin-gs-2026-r1','A','alias_validado_revisao_v2','BYD DOLPHIN GS 180EV',2026))
        affected=cur.rowcount
        stamp=datetime.now(timezone.utc).isoformat()
        note='PBE Veicular 2026 identifica Dolphin GS 180EV; ficha BYD GS de 09/07/2026 confirma bateria 44,9 kWh. Aplicação restrita a 2026. Base original preservada em data/i9.db.'
        target.execute('INSERT INTO match_modelo (raw_name,vehicle_year,model_id,score,method,status,approver,notes,created_at) VALUES (?,?,?,?,?,?,?,?,?)',
            ('BYD DOLPHIN GS 180EV',2026,model_id,1.0,'alias_validado_revisao_v2','APROVADO','Revisão técnica do projeto',note,stamp))
        after=target.execute('SELECT reference,SUM(quantity) FROM frota_snapshot GROUP BY reference ORDER BY reference').fetchall()
        assert before==after
        details={'type':'derived_dataset_revision','parent_database':'data/i9.db','affected_rows':affected,'fleet_totals_unchanged':True,'reason':note}
        target.execute('INSERT INTO etl_execucao (id,started_at,finished_at,status,stage,details) VALUES (?,?,?,?,?,?)',
            (str(uuid.uuid4()),stamp,stamp,'SUCESSO','Revisão técnica em nova versão da base',json.dumps(details,ensure_ascii=False)))
        target.commit()
    config=ROOT/'.env'
    lines=[l for l in config.read_text(encoding='utf-8').splitlines() if not l.startswith('DATABASE_URL=')]
    lines.append('DATABASE_URL=sqlite:///'+destination.as_posix())
    config.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    (ROOT/'docs/dataset-revision.json').write_text(json.dumps({**details,'created_at':stamp,'new_database':str(destination),'totals':after},ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Revision created: {affected} associations verified; quantities and original database preserved.')

if __name__=='__main__':revise()
