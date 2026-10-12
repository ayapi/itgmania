"""Start the local API before game/OBS startup; reuse the existing v3 server."""
from pathlib import Path
from urllib.request import urlopen
import json, subprocess, sys, time, os

directory = Path(__file__).resolve().parent

def running():
    try:
        with urlopen('http://127.0.0.1:8765/api/info', timeout=.25) as response:
            info = json.load(response)
            return info.get('api_version') == 3 and os.path.normcase(info.get('runtime','')) == os.path.normcase(str(directory.parent.resolve()))
    except (OSError, ValueError):
        return False

if not running():
    options = dict(creationflags=subprocess.CREATE_NO_WINDOW) if sys.platform == 'win32' else {}
    with (directory/'api.log').open('ab') as out, (directory/'api-error.log').open('ab') as err:
        process = subprocess.Popen([sys.executable, '-u', str(directory/'bridge.py'),
                                    '--outfox', str(directory.parent)],
                                   cwd=directory.parent, stdout=out, stderr=err, **options)
    for _ in range(15):
        if running():
            break
        if process.poll() is not None:
            raise SystemExit('API startup failed; see Stream/api-error.log')
        time.sleep(.1)
