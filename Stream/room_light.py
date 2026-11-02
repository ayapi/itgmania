"""A separate, resizable TV room light, driven by GiftAPI's musical clock."""
from __future__ import annotations
import argparse
import json
import math
import queue
import threading
import time
from pathlib import Path
from urllib.request import urlopen

BLUE=(110,210,255)
ORANGE=(255,112,18)

class BeatLight:
    def __init__(self): self.clock=None

    def sync(self,status,received_at,network_seconds=0):
        self.clock=None
        if status.get('protocol_version')!=5 or not status.get('ready') or status.get('connected') is False: return
        try:
            beat=float(status['song_beat']);bpm=float(status['effective_bpm'])
            age=float(status.get('snapshot_age_seconds',0))
            if not all(math.isfinite(v) for v in (beat,bpm,age)) or bpm<=0 or age>1.5: return
        except (ValueError,TypeError,KeyError): return
        beat+=(max(0,age)+max(0,network_seconds))*bpm/60
        trial=(status.get('trial_state') or {}).get('trial')
        self.clock=(beat,bpm,received_at,ORANGE if trial else BLUE)

    def color(self,now):
        if self.clock is None or now-self.clock[2]>1.5: return self.rgb(BLUE,1)
        beat,bpm,at,color=self.clock
        phase=(beat+(now-at)*bpm/60+1e-9)%1
        # Immediate beat accent, followed by a smooth fall to a visible floor.
        strength=(.55+.45*math.exp(-phase*4)) if color==BLUE else (.22+.78*math.exp(-phase*7))
        return self.rgb(color,strength)

    @staticmethod
    def rgb(color,strength): return '#'+''.join(f'{round(v*strength):02x}' for v in color)


def listen(mailbox,stop,url):
    while not stop.is_set():
        started=time.monotonic()
        try:
            with urlopen(url,timeout=.7) as response: status=json.load(response)
            if not isinstance(status,dict): status={}
        except (OSError,ValueError): status={}
        now=time.monotonic()
        try: mailbox.get_nowait()
        except queue.Empty: pass
        mailbox.put((status,now,(now-started)/2))
        stop.wait(.2)


class RoomLight:
    def __init__(self,root):
        import tkinter as tk
        self.directory=Path(root)/'Save/GiftAPI';self.directory.mkdir(parents=True,exist_ok=True)
        self.path=self.directory/'room-light.json'
        try: saved=json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError,ValueError): saved={}
        self.root=tk.Tk();self.root.title('ITGmania 部屋の照明 — F11:全画面 / Esc:戻す / F9:裏へ')
        self.root.configure(background=BeatLight.rgb(BLUE,1));self.root.minsize(320,200)
        self.root.geometry(f"{max(320,int(saved.get('width',1400)))}x{max(200,int(saved.get('height',900)))}+60+60")
        self.light=BeatLight();self.stop=threading.Event();self.mailbox=queue.Queue();self.last_color=None
        self.normal=None;self.save_timer=None;self.fullscreen=False;self.saved=saved
        self.root.bind('<F11>',lambda _:self.toggle_fullscreen())
        self.root.bind('<Escape>',lambda _:self.set_fullscreen(False))
        self.root.bind('<F9>',lambda _:self.behind())
        self.root.bind('<Configure>',self.configured)
        self.root.protocol('WM_DELETE_WINDOW',self.close)
        self.root.after(100,self.restore)
        self.root.after(33,self.paint)
        threading.Thread(target=listen,args=(self.mailbox,self.stop,'http://127.0.0.1:8765/api/status'),daemon=True).start()

    def window_api(self):
        import ctypes
        from ctypes import wintypes
        user=ctypes.WinDLL('user32',use_last_error=True)
        user.GetAncestor.argtypes=[wintypes.HWND,wintypes.UINT];user.GetAncestor.restype=wintypes.HWND
        user.SetWindowPos.argtypes=[wintypes.HWND,wintypes.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,wintypes.UINT]
        user.GetWindowRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
        return user,user.GetAncestor(self.root.winfo_id(),2)

    def restore(self):
        import os
        if os.name=='nt' and 'x' in self.saved and 'y' in self.saved:
            user,hwnd=self.window_api()
            # Absolute desktop coordinates also support a TV left of the main monitor.
            user.SetWindowPos(hwnd,None,int(self.saved['x']),int(self.saved['y']),0,0,0x15)
        self.remember()
        if self.saved.get('fullscreen'): self.set_fullscreen(True)
        elif self.saved.get('maximized'): self.root.state('zoomed')
        self.behind()

    def remember(self):
        if self.fullscreen or self.root.state()!='normal': return
        import os
        x,y=self.root.winfo_x(),self.root.winfo_y()
        if os.name=='nt':
            import ctypes
            from ctypes import wintypes
            user,hwnd=self.window_api();rect=wintypes.RECT()
            if user.GetWindowRect(hwnd,ctypes.byref(rect)): x,y=rect.left,rect.top
        self.normal=dict(x=x,y=y,width=self.root.winfo_width(),height=self.root.winfo_height())

    def configured(self,event):
        if event.widget is not self.root: return
        if self.save_timer: self.root.after_cancel(self.save_timer)
        self.save_timer=self.root.after(500,self.save)

    def save(self):
        self.save_timer=None;self.remember()
        value=dict(self.normal or {},fullscreen=self.fullscreen,maximized=self.root.state()=='zoomed' and not self.fullscreen)
        from bridge import atomic_json
        atomic_json(self.path,value)

    def set_fullscreen(self,enabled):
        if enabled==self.fullscreen: return
        self.remember();self.fullscreen=enabled
        self.root.attributes('-fullscreen',enabled)
        self.root.after(100,self.save)

    def toggle_fullscreen(self): self.set_fullscreen(not self.fullscreen)

    def behind(self):
        import os
        if os.name=='nt':
            user,hwnd=self.window_api()
            user.SetWindowPos(hwnd,1,0,0,0,0,0x13)  # HWND_BOTTOM; no move, size or activation.
        else: self.root.lower()

    def paint(self):
        try:
            while True: self.light.sync(*self.mailbox.get_nowait())
        except queue.Empty: pass
        color=self.light.color(time.monotonic())
        if color!=self.last_color: self.root.configure(background=color);self.last_color=color
        self.root.after(33,self.paint)

    def close(self):
        self.save();self.stop.set()
        for timer in self.root.tk.call('after','info'): self.root.after_cancel(timer)
        self.root.destroy()

    def run(self): self.root.mainloop()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--test-seconds',type=float,help=argparse.SUPPRESS)
    args=parser.parse_args();directory=args.root/'Save/GiftAPI';directory.mkdir(parents=True,exist_ok=True)
    # The handle stays open for the window lifetime; repeated launchers reuse it.
    with (directory/'room-light.lock').open('a+b') as guard:
        import os
        if os.name=='nt':
            import msvcrt
            if guard.tell()==0: guard.write(b'0');guard.flush()
            guard.seek(0)
            try: msvcrt.locking(guard.fileno(),msvcrt.LK_NBLCK,1)
            except OSError: return
        app=RoomLight(args.root)
        if args.test_seconds: app.root.after(round(args.test_seconds*1000),app.close)
        app.run()

if __name__=='__main__':main()
