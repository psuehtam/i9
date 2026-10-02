"""Local lifecycle, PostgreSQL backup and isolated restore verification."""
import argparse,ctypes,hashlib,json,os,shutil,socket,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
from sqlalchemy import create_engine,select,update,text
from src import db,operational_schema as o

ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/'data/runtime'

def hidden_process_options():
    """Prevent background maintenance commands from opening a console on Windows."""
    return {'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}

def run_hidden(command,**kwargs):
    return subprocess.run(command,**hidden_process_options(),**kwargs)

def process_exists(pid):
    if os.name=='nt':
        try:
            kernel32=ctypes.WinDLL('kernel32',use_last_error=True)
            kernel32.OpenProcess.argtypes=(ctypes.c_uint32,ctypes.c_bool,ctypes.c_uint32)
            kernel32.OpenProcess.restype=ctypes.c_void_p
            handle=kernel32.OpenProcess(0x1000,False,int(pid))
            if not handle:return False
            kernel32.CloseHandle(handle)
            return True
        except (OSError,TypeError,ValueError):
            return False
    try:
        os.kill(int(pid),0)
        return True
    except (OSError,TypeError,ValueError):
        return False

def pg_bin():
    if os.getenv('I9_PG_BIN'):return Path(os.environ['I9_PG_BIN'])
    local=RUNTIME/'pgsql/bin'
    if local.exists():return local
    binary=shutil.which('pg_dump')
    if binary:return Path(binary).parent
    raise RuntimeError('Configure I9_PG_BIN com o diretório PostgreSQL.')

def pg_command(name,*args):
    url=db.engine.url
    if url.get_backend_name()!='postgresql':raise RuntimeError('Operação exige PostgreSQL configurado.')
    binary=pg_bin()/(name+('.exe' if os.name=='nt' else ''))
    return run_hidden([str(binary),'-h',url.host or '127.0.0.1','-p',str(url.port or 5432),'-U',url.username or 'i9',*map(str,args)],
        env=dict(os.environ,PGPASSWORD=url.password or ''),check=True,capture_output=True,text=True)

def record(key,value):
    from src.fleet_publication import insert_once
    stamp=datetime.now(timezone.utc).isoformat()
    with db.engine.begin() as c:
        insert_once(c,o.setting,dict(key=key,value=value,updated_at=stamp),['key'])
        c.execute(update(o.setting).where(o.setting.c.key==key).values(value=value,updated_at=stamp))

def backup(destination=None):
    from src import pipeline_schema as p
    folder=Path(destination or os.getenv('I9_BACKUP_DIR') or ROOT/'data/backups')/datetime.now().strftime('postgres-%Y%m%d-%H%M%S')
    folder.mkdir(parents=True,exist_ok=False)
    try:
        pg_command('pg_dump','-d',db.engine.url.database,'-Fc','-f',folder/'database.dump')
        with db.engine.connect() as c:
            files=[dict(r) for r in c.execute(select(p.artifact.c.path,p.artifact.c.raw_sha256,p.artifact.c.bytes)).mappings()]
        originals=folder.parent/'originals';originals.mkdir(exist_ok=True)
        unique={item['raw_sha256']:item for item in files}
        files=[]
        for digest,item in unique.items():
            target=originals/(digest+'.raw')
            if not target.exists():
                temporary=target.with_suffix('.copy');shutil.copyfile(item['path'],temporary);temporary.replace(target)
            files.append(dict(item,backup_path=str(target.resolve())))
        manifest={'created_at':datetime.now(timezone.utc).isoformat(),'database':db.engine.url.database,'files':files,'dump':'database.dump'}
        (folder/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
        pg_command('pg_restore','--list',folder/'database.dump')
        record('backup',{'status':'ok','last_success_at':manifest['created_at'],'path':str(folder)})
        parent=folder.parent.resolve();cutoff=datetime.now().timestamp()-30*86400
        for old in parent.glob('postgres-*'):
            resolved=old.resolve()
            if resolved.parent==parent and resolved.is_dir() and (resolved/'manifest.json').is_file() and resolved.stat().st_mtime<cutoff:
                shutil.rmtree(resolved)
        print('Backup validado:',folder,flush=True)
        return folder
    except Exception:
        record('backup',{'status':'failed','path':str(folder)})
        raise

def restore_test(folder):
    import hashlib
    folder=Path(folder).resolve();manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    for artifact in manifest['files']:
        path=Path(artifact.get('backup_path') or artifact['path']);path=path if path.is_absolute() else ROOT/path
        with path.open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest()!=artifact['raw_sha256']:raise RuntimeError('Original ausente/corrompido: '+str(path))
    name='i9_restore_'+datetime.now().strftime('%Y%m%d%H%M%S')
    pg_command('createdb',name)
    restored=None
    try:
        pg_command('pg_restore','-d',name,'--exit-on-error',folder/'database.dump')
        restored=create_engine(db.engine.url.set(database=name))
        original_engine=db.engine
        try:
            from src import pipeline
            db.engine=restored
            pipeline.reset_epoch()
        finally:db.engine=original_engine
        with restored.connect() as c:
            counts={table:c.execute(text('SELECT count(*) FROM '+table)).scalar() for table in
                ('vehicle_asset','registry_vehicle','battery_asset','vehicle_battery_installation','passport_dossier')}
        report={'database':name,'counts':counts,'checked_at':datetime.now(timezone.utc).isoformat(),'result':'ok'}
        (folder/'restore-test.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print('Restauração isolada verificada:',counts,flush=True)
    finally:
        if restored:restored.dispose()
        pg_command('dropdb',name)

def start_database():
    cluster=RUNTIME/'postgres-data'
    if not (cluster/'PG_VERSION').exists():return
    pg=pg_bin()/('pg_ctl.exe' if os.name=='nt' else 'pg_ctl')
    result=run_hidden([str(pg),'-D',str(cluster),'status'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    if result.returncode:
        cfg=json.loads((RUNTIME/'local-postgres.json').read_text())
        run_hidden([str(pg),'-D',str(cluster),'-l',str(RUNTIME/'postgres.log'),'-o',f'-p {cfg["port"]} -h 127.0.0.1','start'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True,timeout=60)

def ensure_services():
    import httpx
    logs=ROOT/'data/logs';logs.mkdir(parents=True,exist_ok=True)
    flags=hidden_process_options().get('creationflags',0)
    try:
        response=httpx.get('http://127.0.0.1:3000/health',timeout=2,trust_env=False)
        if response.json().get('database')!='postgresql':raise RuntimeError('Porta 3000 ocupada por outra aplicação')
        running=True
    except (httpx.ConnectError,httpx.ConnectTimeout):running=False
    children={}
    if not running:
        with (logs/'api.log').open('ab') as output:
            children['api']=subprocess.Popen([sys.executable,'-m','uvicorn','src.api.main:app','--host','127.0.0.1','--port','3000'],cwd=ROOT,stdout=output,stderr=output,creationflags=flags).pid
    with db.engine.connect() as c:health=c.execute(select(o.setting.c.value).where(o.setting.c.key=='worker')).scalar() or {}
    stamp=health.get('checked_at');alive=bool(stamp) and (datetime.now(timezone.utc)-datetime.fromisoformat(stamp)).total_seconds()<90
    if alive and health.get('hostname')==socket.gethostname():alive=process_exists(health.get('pid'))
    if not alive:
        with (logs/'worker-console.log').open('ab') as output:
            children['worker']=subprocess.Popen([sys.executable,'-m','src.worker'],cwd=ROOT,stdout=output,stderr=output,creationflags=flags).pid
    (RUNTIME/'processes.json').write_text(json.dumps(children),encoding='utf-8')
    return children

def start():
    RUNTIME.mkdir(parents=True,exist_ok=True)
    start_database()
    run_hidden([sys.executable,'-m','alembic','upgrade','head'],cwd=ROOT,check=True)
    ensure_services()
    print('Aplicação: http://localhost:3000')

def acquire_supervisor_mutex():
    """Allow only one supervisor, including simultaneous Task Scheduler starts."""
    if os.name!='nt':return None
    kernel32=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel32.CreateMutexW.argtypes=(ctypes.c_void_p,ctypes.c_bool,ctypes.c_wchar_p)
    kernel32.CreateMutexW.restype=ctypes.c_void_p
    suffix=hashlib.sha256(str(ROOT).lower().encode()).hexdigest()[:12]
    handle=kernel32.CreateMutexW(None,True,'Local\\i9-supervisor-'+suffix)
    if not handle:raise ctypes.WinError(ctypes.get_last_error())
    if ctypes.get_last_error()==183:
        kernel32.CloseHandle(handle)
        return False
    return handle

def supervise():
    import time
    RUNTIME.mkdir(exist_ok=True)
    mutex=acquire_supervisor_mutex()
    if mutex is False:return
    try:
        start()
        while True:
            # Give newly launched API and worker time to publish their health
            # before checking them again. This avoids a second launch race.
            time.sleep(60)
            try:
                # Migrations run once at startup. The recurring check only revives
                # services and therefore stays silent and inexpensive.
                try:
                    with db.engine.connect() as connection:connection.execute(text('SELECT 1'))
                except Exception:
                    db.engine.dispose()
                    start_database()
                    db.engine.dispose()
                    with db.engine.connect() as connection:connection.execute(text('SELECT 1'))
                ensure_services()
                from src import pipeline
                pipeline.schedule_due()
                record('supervisor',{'status':'running','pid':os.getpid()})
            except Exception as error:
                import logging
                logging.exception('Supervisor tentará recuperar os serviços: %s',error)
    finally:
        if mutex:
            kernel32=ctypes.WinDLL('kernel32')
            kernel32.ReleaseMutex(mutex)
            kernel32.CloseHandle(mutex)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['start','supervise','backup','restore-test']);parser.add_argument('--path');args=parser.parse_args()
    if args.action=='supervise':supervise()
    elif args.action=='start':start()
    elif args.action=='backup':backup(args.path)
    elif not args.path:parser.error('--path é obrigatório')
    else:restore_test(args.path)

if __name__=='__main__':main()
