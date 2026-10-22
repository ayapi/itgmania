"""OneComme websocket -> existing GiftAPI. No third-party Python dependencies."""
from __future__ import annotations
import argparse
import base64
from datetime import datetime
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import shutil
import select
import socket
import struct
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
import uuid
from bridge import atomic_json


def integer(value, maximum=10**12):
    if isinstance(value, bool): return None
    try:
        n=int(value)
        return n if n>=0 and n<=maximum and float(value)==n else None
    except (ValueError, TypeError, OverflowError): return None


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


class GiftImage(HTMLParser):
    def __init__(self):
        super().__init__(); self.file=None

    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if tag=='img' and 'gift-image' in a.get('class','').split():
            path=urlsplit(a.get('src','')).path
            if '/gift/assets/' in path: self.file=path.rsplit('/',1)[-1].split('=')[0]


def gift(comment):
    """Use structured gift flags; never execute HTML or match ordinary chat text."""
    platform=comment.get('service'); data=comment.get('data') or {}
    if not isinstance(data,dict): return None
    meta=comment.get('meta') or {}
    if not isinstance(meta,dict): meta={}
    if not data.get('hasGift') or meta.get('free') or data.get('free'): return None
    if platform=='tiktok':
        g=data.get('gift') or {}
        if not isinstance(g,dict): return None
        key=str(g.get('giftId','')); count=integer(g.get('repeatCount',1),1000000)
    elif platform=='youtube' and data.get('giftType')=='jewel':
        parser=GiftImage(); parser.feed(data.get('comment',''))
        key=parser.file
        # Fallback for the captured yt-<sender>-<filename>#<transaction> form.
        if not key:
            import re
            match=re.search(r'-([^-/#]+\.png)#',str(data.get('giftId','')))
            key=match.group(1) if match else None
        count=integer(data.get('giftCount',1),1000000)
    else: return None  # A paid YouTube heart is a gift, not a free reaction.
    return (platform,key,count) if key and count else None


def service_platform(service):
    value=str(service.get('service') or service.get('name') or '').lower()
    if value in ('tiktok','youtube'): return value
    url=str((service.get('meta') or {}).get('url') or service.get('url') or '')
    host=(urlsplit(url).hostname or '').lower()
    if host.endswith('tiktok.com'): return 'tiktok'
    if host.endswith('youtube.com') or host=='youtu.be': return 'youtube'
    return None


class Router:
    def __init__(self, root, send, clock=time.time):
        self.directory=Path(root)/'Save/GiftAPI'; self.directory.mkdir(parents=True,exist_ok=True)
        self.path=self.directory/'onecomme-state.json'; self.send=send; self.clock=clock
        mapping=self.directory/'gift-map.json'
        if not mapping.exists(): shutil.copy2(Path(__file__).with_name('gift-map.json'),mapping)
        if self.path.exists(): self.state=json.loads(self.path.read_text(encoding='utf-8-sig'))
        else: self.state=dict(initialized=False,cutoff=clock(),seen={},pending={},services={},likes={})
        self.last_error=None; self.last_event=None
        self.dirty=False

    def save(self): atomic_json(self.path,self.state)

    def queue(self, key, kind, body, free=False):
        self.state['pending'][key]=dict(kind=kind,body=body,expires=self.clock()+1.5 if free else None)
        self.dirty=True

    def comments(self, rows, seed=False, history=False):
        mapping=json.loads((self.directory/'gift-map.json').read_text(encoding='utf-8-sig'))
        for c in rows:
            if not isinstance(c,dict): continue
            g=gift(c)
            if not g: continue
            platform,key,count=g; data=c['data']
            if not isinstance(data.get('id'),str) or not data['id']: continue
            identity=digest([platform,data.get('liveId'),data['id'],key])
            old=self.state['seen'].get(identity,0)
            if count<=old: continue
            if len(self.state['seen'])>=100000 and identity not in self.state['seen']:
                raise ValueError('onecomme-state.json receipt capacity reached; archive between streams')
            if history and not seed:
                try: timestamp=datetime.fromisoformat(data['timestamp'].replace('Z','+00:00')).timestamp()
                except (KeyError,ValueError,TypeError): continue
                if timestamp<self.state['cutoff']: seed_row=True
                else: seed_row=False
            else: seed_row=seed
            self.state['seen'][identity]=count
            self.dirty=True
            if seed_row: continue
            if key not in mapping.get(platform,{}):
                self.state['unmapped']=dict(platform=platform,gift_id=key,count=count)
                continue
            sender=''.join(ch for ch in str(data.get('displayName') or data.get('name') or '視聴者') if ord(ch)>=32)[:80]
            for start in range(old,count,256):
                end=min(start+256,count)
                event_id='onecomme-gift-'+digest([identity,start,end])
                self.queue(event_id,'gift',dict(event_id=event_id,platform=platform,gift_id=key,sender=sender,count=end-start))

    def services(self, rows, reset=False):
        if reset: self.state['services']={}; self.dirty=True
        if not isinstance(rows,list): return
        for s in rows:
            if not isinstance(s,dict) or not s.get('id'): continue
            previous=self.state['services'].get(s['id'],{})
            meta=dict(previous.get('meta') or {}); meta.update(s.get('meta') or {})
            item=dict(previous); item.update({k:v for k,v in s.items() if k in ('id','name','service','url','enabled')})
            item['meta']={k:v for k,v in meta.items() if k in ('url','viewer','isLive','totalLikeCount','startTime')}
            if item!=previous:
                self.state['services'][s['id']]=item; self.dirty=True

    def metadata(self, data):
        if isinstance(data,list): self.services(data); return
        if not isinstance(data,dict): return
        if isinstance(data.get('services'),list): self.services(data['services']); return
        if data.get('id'):
            self.services([data if 'meta' in data else dict(id=data['id'],meta=data)]); return
        # Raw meta events can be keyed by the OneComme service ID.
        keyed=[dict(id=k,meta=v) for k,v in data.items() if k in self.state['services'] and isinstance(v,dict)]
        if keyed: self.services(keyed); return
        inferred=service_platform(dict(meta=data))
        candidates=[s for s in self.state['services'].values() if s.get('enabled') and
                    (not inferred or service_platform(s)==inferred) and
                    ('totalLikeCount' not in data or service_platform(s)=='tiktok')]
        if len(candidates)==1: self.services([dict(id=candidates[0]['id'],meta=data)])

    def publish_meta(self, reset=False):
        audience=dict(tiktok=0,youtube=0)
        for s in self.state['services'].values():
            platform=service_platform(s); meta=s.get('meta') or {}
            if not platform or not s.get('enabled') or meta.get('isLive') is False: continue
            count=integer(meta.get('viewer'),10000000)
            if count is not None: audience[platform]+=count
            if platform=='tiktok':
                total=integer(meta.get('totalLikeCount'))
                if total is None: continue
                stream=digest([meta.get('url') or s.get('url'),meta.get('startTime')])[:32]
                value=[stream,total]
                if reset or self.state['likes'].get(s['id'])!=value:
                    self.state['likes'][s['id']]=value
                    body=dict(event_id='onecomme-like-'+str(uuid.uuid4()),platform='tiktok',stream_id=stream,total=total,reset=reset)
                    self.queue('likes-'+s['id'],'hearts',body,free=True)
        if reset or audience!=self.state.get('audience'):
            self.state['audience']=audience
            self.queue('audience','audience',audience)

    def handle(self, message):
        if not isinstance(message,dict): return
        self.dirty=False
        kind=message.get('type'); data=message.get('data')
        self.last_event=kind
        if kind=='connected' and isinstance(data,dict):
            initial=not self.state['initialized']
            if initial: self.state['cutoff']=self.clock()
            self.comments(data.get('comments',[]),seed=initial,history=True)
            self.state['initialized']=True
            self.services(data.get('services',[]),reset=True)
            self.publish_meta(reset=True)
        elif kind in ('comment','comments'):
            rows=data if isinstance(data,list) else data.get('comments',[data]) if isinstance(data,dict) else []
            initial=isinstance(data,dict) and (data.get('options') or {}).get('init') is True
            self.comments(rows,seed=initial)
            for c in rows:
                if isinstance(c,dict) and isinstance(c.get('serviceData'),dict):
                    # Only update metadata when present; cached disabled flags on
                    # old comment wrappers must not disable a live connection.
                    s=c['serviceData']
                    if s.get('meta'): self.metadata(dict(id=s.get('id'),meta=s['meta']))
            self.publish_meta()
        elif kind=='services': self.services(data if isinstance(data,list) else data.get('services',[]),reset=True); self.publish_meta()
        elif kind=='meta': self.metadata(data); self.publish_meta()
        elif kind=='meta.clear':
            for s in self.state['services'].values(): s['meta']={}
            self.dirty=True
            self.publish_meta()
        elif kind=='reactions' and isinstance(data,dict):
            rows=[]
            for r in data.get('reactions',[]):
                value=integer(r.get('value'),10000000) if isinstance(r,dict) else None
                if value is not None and isinstance(r.get('key'),str): rows.append(dict(key=r['key'],value=value))
            if rows:
                event_id='onecomme-reaction-'+str(uuid.uuid4())
                self.queue(event_id,'hearts',dict(event_id=event_id,platform='youtube',reactions=rows,effect=bool(data.get('effect'))),free=True)
        else: return
        if self.dirty: self.save()

    def flush(self):
        changed=False
        for key,entry in list(self.state['pending'].items())[:32]:
            if entry['expires'] is not None and self.clock()>entry['expires']:
                del self.state['pending'][key]; changed=True; continue
            try:
                self.send(entry['kind'],entry['body'])
            except (OSError,ValueError) as error:
                self.last_error=str(error)
                # Paid gifts remain durable with the same event ID for retry.
                if entry['expires'] is not None: del self.state['pending'][key]; changed=True
                if isinstance(error,HTTPError): continue
                break
            else:
                del self.state['pending'][key]; changed=True; self.last_error=None
        if changed: self.save()


class WebSocket:
    def __init__(self,url):
        u=urlsplit(url)
        if u.scheme!='ws' or not u.hostname: raise ValueError('websocket_url must be ws://host:port/path')
        self.socket=socket.create_connection((u.hostname,u.port or 80),timeout=3)
        self.socket.settimeout(60); self.buffer=b''
        try:
            key=base64.b64encode(os.urandom(16)).decode()
            target=(u.path or '/')+('?' + u.query if u.query else '')
            request=(f'GET {target} HTTP/1.1\r\nHost: {u.netloc}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n')
            self.socket.sendall(request.encode('ascii'))
            while b'\r\n\r\n' not in self.buffer:
                chunk=self.socket.recv(4096)
                if not chunk: raise OSError('WebSocket handshake closed')
                self.buffer+=chunk
                if len(self.buffer)>65536: raise ValueError('WebSocket headers too large')
            header,self.buffer=self.buffer.split(b'\r\n\r\n',1)
            lines=header.decode('ascii').split('\r\n')
            fields=dict((k.lower(),v.strip()) for k,v in (line.split(':',1) for line in lines[1:] if ':' in line))
            expected=base64.b64encode(hashlib.sha1((key+'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest()).decode()
            if ' 101 ' not in lines[0] or fields.get('sec-websocket-accept')!=expected: raise OSError('WebSocket upgrade rejected')
        except Exception:
            self.close(); raise

    def exact(self,size):
        while len(self.buffer)<size:
            chunk=self.socket.recv(max(4096,size-len(self.buffer)))
            if not chunk: raise OSError('OneComme disconnected')
            self.buffer+=chunk
        value,self.buffer=self.buffer[:size],self.buffer[size:]
        return value

    def receive(self):
        parts=bytearray()
        while True:
            first,second=self.exact(2); opcode=first&15
            size=second&127
            if size==126: size=struct.unpack('!H',self.exact(2))[0]
            elif size==127: size=struct.unpack('!Q',self.exact(8))[0]
            if size+len(parts)>16*1024*1024: raise ValueError('OneComme frame too large')
            mask=self.exact(4) if second&128 else None
            payload=self.exact(size)
            if mask: payload=bytes(v^mask[i%4] for i,v in enumerate(payload))
            if opcode==8: raise OSError('OneComme closed the socket')
            if opcode==9:
                mask=os.urandom(4)
                self.socket.sendall(bytes([0x8A,0x80|len(payload)])+mask+bytes(v^mask[i%4] for i,v in enumerate(payload)))
                continue
            if opcode==10: continue
            if opcode not in (0,1): raise ValueError('Expected a JSON text frame')
            parts.extend(payload)
            if first&128: return json.loads(parts.decode('utf-8'))

    def close(self): self.socket.close()


def config(root):
    path=Path(root)/'Save/GiftAPI/onecomme.json'
    path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists(): shutil.copy2(Path(__file__).with_name('onecomme.json'),path)
    return json.loads(path.read_text(encoding='utf-8-sig'))


def run(root):
    from contextlib import ExitStack
    directory=Path(root)/'Save/GiftAPI'; directory.mkdir(parents=True,exist_ok=True)
    with ExitStack() as stack:
        lock=stack.enter_context((directory/'onecomme.lock').open('a+b'))
        if not lock.tell(): lock.write(b'0'); lock.flush()
        lock.seek(0)
        if os.name=='nt':
            import msvcrt
            try: msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
            except OSError: return
        else:
            import fcntl
            try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except OSError: return
        cfg=config(root)
        def send(kind,body):
            request=Request(cfg['api_url'].rstrip('/')+'/api/'+kind,json.dumps(body,ensure_ascii=False).encode(),{'Content-Type':'application/json'},method='POST')
            with urlopen(request,timeout=2) as response: return json.load(response)
        router=Router(root,send)
        def status(connected,error=None):
            atomic_json(directory/'onecomme-status.json',dict(pid=os.getpid(),connected=connected,websocket_url=cfg['websocket_url'],
                pending=len(router.state['pending']),last_event=router.last_event,error=error or router.last_error,updated_at=time.time()))
        last_log=None
        while True:
            cfg=config(root)
            if not cfg.get('enabled',True): status(False,'disabled'); return
            ws=None
            try:
                router.flush(); ws=WebSocket(cfg['websocket_url']); status(True)
                print('OneComme connected',flush=True); last_log=None
                while True:
                    router.flush()
                    if not ws.buffer and not select.select([ws.socket],[],[],.25)[0]:
                        status(True); continue
                    router.handle(ws.receive()); router.flush(); status(True)
            except (OSError,ValueError,KeyError,TypeError) as error:
                status(False,str(error))
                text=type(error).__name__+': '+str(error)
                if text!=last_log: print(text,flush=True); last_log=text
                time.sleep(max(.5,float(cfg.get('reconnect_seconds',2))))
            finally:
                if ws: ws.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parent.parent)
    run(parser.parse_args().root.resolve())
