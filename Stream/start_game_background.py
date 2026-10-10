"""Start the game and its position tracker without leaving a terminal open."""
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parent
with (root/'window-position-error.log').open('ab') as err:
    subprocess.Popen([sys.executable, str(root/'start_game.py'), *sys.argv[1:]],
                     cwd=root, stdout=err, stderr=err,
                     creationflags=subprocess.CREATE_NO_WINDOW)
