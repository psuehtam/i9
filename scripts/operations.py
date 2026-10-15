"""Local process lifecycle."""
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
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['start','supervise']);parser.add_argument('--path');args=parser.parse_args()
    if args.action=='supervise':supervise()
    elif args.action=='start':start()

if __name__=='__main__':main()
