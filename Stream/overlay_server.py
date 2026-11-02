"""Read-only LAN overlay server. The command API remains on loopback:8765."""
from __future__ import annotations
import argparse
import hashlib
import json
import threading
import time
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlsplit
from urllib.request import urlopen
from prepare_platform_overlays import build

PUBLIC_FIELDS={'protocol_version','ready','connected','reason','session','native_trial_panel',
 'song_title','song_artist','song','song_beat','effective_bpm','base_bpm','snapshot_age_seconds',
 'trial_state','gift_menu','bpm_offset_limit'}

class DisplayState:
    def __init__(self):
        self.lock=threading.Lock();self.snapshot={};self.received=0
    def update(self,status,now=None):
        public={k:v for k,v in status.items() if k in PUBLIC_FIELDS}
        with self.lock:self.snapshot=public;self.received=time.monotonic() if now is None else now
    def get(self,now=None):
        now=time.monotonic() if now is None else now
        with self.lock:status=dict(self.snapshot);elapsed=max(0,now-self.received)
        status['snapshot_age_seconds']=max(0,float(status.get('snapshot_age_seconds') or 0))+elapsed
        if elapsed>1.5:status.update(ready=False,connected=False)
        return status
    def collect(self,stop):
        while not stop.is_set():
            try:
                with urlopen('http://127.0.0.1:8765/api/status',timeout=.7) as response:status=json.load(response)
                if isinstance(status,dict):self.update(status)
            except (OSError,ValueError):self.update(dict(ready=False,connected=False))
            stop.wait(.2)

def identity(root):return hashlib.sha256(str(Path(root).resolve()).casefold().encode()).hexdigest()[:24]

def handler(directory,state,root):
    directory=Path(directory)
    class Handler(BaseHTTPRequestHandler):
        def send(self,data,content_type='application/json; charset=utf-8',status=200):
            self.send_response(status);self.send_header('Content-Type',content_type)
            self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store')
            self.end_headers();self.wfile.write(data)
        def do_GET(self):
            path=urlsplit(self.path).path.rstrip('/')
            if path=='/health':self.send(json.dumps(dict(service='itgmania-overlay',instance=identity(root))).encode())
            elif path=='/api/status':self.send(json.dumps(state.get(),ensure_ascii=False,allow_nan=False).encode('utf-8'))
            elif path in ('/tiktok','/youtube','/overlay-tiktok.html','/overlay-youtube.html','/light'):
                if path=='/light':
                    html=(directory/'overlay.html').read_text(encoding='utf-8-sig').replace('<title>', '<meta name="stream-mode" content="light"><title>',1)
                    data=html.encode('utf-8')
                else:
                    name='tiktok' if 'tiktok' in path else 'youtube'
                    data=(directory/f'overlay-{name}.html').read_bytes()
                self.send(data,'text/html; charset=utf-8')
            else:self.send(b'{"error":"Not found"}',status=404)
        def do_POST(self):self.send(b'{"error":"Display only"}',status=405)
        def log_message(self,*args):pass
    return Handler

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--port',type=int,default=8766);args=parser.parse_args()
    directory=Path(__file__).resolve().parent;build(directory)
    save=args.root/'Save/GiftAPI';save.mkdir(parents=True,exist_ok=True)
    with (save/'overlay-server.lock').open('a+b') as guard:
        import msvcrt
        if not guard.tell():guard.write(b'0');guard.flush()
        guard.seek(0)
        try:msvcrt.locking(guard.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:return
        state=DisplayState();stop=threading.Event()
        threading.Thread(target=state.collect,args=(stop,),daemon=True).start()
        server=ThreadingHTTPServer(('0.0.0.0',args.port),handler(directory,state,args.root))
        print(f'LAN overlay: port {args.port}; /tiktok, /youtube, /light',flush=True)
        try:server.serve_forever()
        finally:stop.set();server.server_close()
if __name__=='__main__':main()
