"""Start the OneComme listener; its file lock prevents duplicate consumers."""
from pathlib import Path
import subprocess,sys

directory=Path(__file__).resolve().parent
options=dict(creationflags=subprocess.CREATE_NO_WINDOW) if sys.platform=='win32' else {}
with (directory/'onecomme.log').open('ab') as out, (directory/'onecomme-error.log').open('ab') as err:
    subprocess.Popen([sys.executable,'-u',str(directory/'onecomme.py')],cwd=directory.parent,stdout=out,stderr=err,**options)
