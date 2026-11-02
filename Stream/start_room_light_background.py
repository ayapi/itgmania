"""Launch the separate visible room-light window without a console."""
from pathlib import Path
import subprocess,sys
source=Path(__file__).resolve().parent
options=dict(creationflags=subprocess.CREATE_NO_WINDOW) if sys.platform=='win32' else {}
with (source/'room-light-error.log').open('ab') as error:
    subprocess.Popen([sys.executable,str(source/'room_light.py')],cwd=source.parent,stdout=error,stderr=error,**options)
