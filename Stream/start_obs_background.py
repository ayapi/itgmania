"""Start the OBS controller alongside the game; its mutex prevents duplicates."""
from pathlib import Path
import subprocess, sys

root = Path(__file__).resolve().parent
options = {}
if sys.platform == 'win32':
    options['creationflags'] = subprocess.CREATE_NO_WINDOW
with (root/'obs-sync.log').open('ab') as out, (root/'obs-sync-error.log').open('ab') as err:
    subprocess.Popen([sys.executable, '-u', str(root/'obs_sync.py')],
                     cwd=root, stdout=out, stderr=err, **options)
