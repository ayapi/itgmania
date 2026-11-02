"""Start the read-only LAN display service without a console."""
from pathlib import Path
from urllib.request import urlopen
import json,subprocess,sys,time
from overlay_server import identity
source=Path(__file__).resolve().parent

def running():
    try:
        with urlopen('http://127.0.0.1:8766/health',timeout=.3) as response:info=json.load(response)
        return info.get('service')=='itgmania-overlay' and info.get('instance')==identity(source.parent)
    except (OSError,ValueError):return False
if not running():
    options=dict(creationflags=subprocess.CREATE_NO_WINDOW) if sys.platform=='win32' else {}
    with (source/'overlay-server.log').open('ab') as out,(source/'overlay-server-error.log').open('ab') as err:
        process=subprocess.Popen([sys.executable,'-u',str(source/'overlay_server.py')],cwd=source.parent,stdout=out,stderr=err,**options)
    for _ in range(20):
        if running():break
        if process.poll() is not None:raise SystemExit('LAN overlay startup failed; see Stream/overlay-server-error.log')
        time.sleep(.1)
    else:raise SystemExit('LAN overlay did not become ready')
