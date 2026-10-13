"""Local HTTP API for the Simply Love GiftAPI gameplay actor (Python 3.10+)."""
from __future__ import annotations
import argparse
import json
import math
import os
import shutil
from pathlib import Path
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, unquote

DEFAULT_ROOT = str(Path(__file__).resolve().parent.parent)

class APIError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message

def numeric(body, key, lower, upper, *, integer=False):
    value = body.get(key)
    try:
        finite = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise APIError(400, f'{key} must be a finite number')
    if not lower <= value <= upper or (integer and value != int(value)):
        raise APIError(400, f'{key} must be between {lower} and {upper}' + (' (integer)' if integer else ''))
    return int(value) if integer else value

def validate(kind, body):
    if not isinstance(body, dict):
        raise APIError(400, 'JSON object required')
    fields = {'notes': {'count'}, 'rescue': {'points'}, 'trial': {'count'}, 'lock': {'count'},
              'hearts': {'count','total','reactions','reset','stream_id','effect'}}
    if kind == 'tempo':
        raise APIError(410, 'Version 5 uses /api/trial and /api/rescue; tempo is retired')
    if kind not in fields:
        raise APIError(400, 'Unknown gift kind')
    allowed = {'event_id','sender','player','platform','gift_id','amount_yen','coins','viewer_count'} | fields[kind]
    if set(body)-allowed:
        raise APIError(400, 'Unknown fields: '+', '.join(sorted(set(body)-allowed)))
    sender=body.get('sender','')
    if not isinstance(sender,str) or len(sender)>80 or any(ord(c)<32 for c in sender):
        raise APIError(400,'sender must be a name of up to 80 characters without control characters')
    if kind!='hearts' and not sender:
        raise APIError(400,'sender is required')
    event_id=body.get('event_id',str(uuid.uuid4()))
    if not isinstance(event_id,str) or not 1<=len(event_id)<=128 or any(ord(c)<32 for c in event_id):
        raise APIError(400,'Invalid event_id')
    player=body.get('player','P1')
    if player not in ('P1','P2'): raise APIError(400,'player must be P1 or P2')
    out=dict(kind=kind,event_id=event_id,sender=sender,player=player)
    for key in ('platform','gift_id','stream_id'):
        if key in body:
            v=body[key]
            if not isinstance(v,str) or len(v)>128 or any(ord(c)<32 for c in v): raise APIError(400,'Invalid '+key)
            out[key]=v
    for key in ('amount_yen','coins','viewer_count'):
        if key in body: out[key]=numeric(body,key,0,10000000,integer=key!='amount_yen')
    if kind in ('notes','trial','lock'):
        out['count']=numeric(dict(count=body.get('count',1)),'count',1,256,integer=True)
    elif kind=='rescue': out['points']=numeric(body,'points',1,10000000,integer=True)
    else:
        if 'effect' in body and not isinstance(body['effect'],bool): raise APIError(400,'effect must be boolean')
        if body.get('platform') not in ('tiktok','youtube'): raise APIError(400,'hearts platform must be tiktok or youtube')
        if body['platform']=='tiktok':
            out['total']=numeric(body,'total',0,1000000000000,integer=True)
            if 'reset' in body and not isinstance(body['reset'],bool): raise APIError(400,'reset must be boolean')
            out['reset']=body.get('reset',False)
            if 'count' in body or 'reactions' in body: raise APIError(400,'TikTok requires cumulative total')
        else:
            if 'total' in body or ('count' in body)==('reactions' in body): raise APIError(400,'YouTube requires count OR reactions')
            if 'reactions' in body:
                reactions=body['reactions']
                if not isinstance(reactions,list) or len(reactions)>256: raise APIError(400,'Invalid reactions')
                total=0
                for r in reactions:
                    if not isinstance(r,dict) or not isinstance(r.get('key'),str): raise APIError(400,'Invalid reaction')
                    total+=numeric(r,'value',0,10000000,integer=True)
                if total>10000000: raise APIError(400,'Too many reactions')
                out['count']=total
            else: out['count']=numeric(body,'count',0,10000000,integer=True)
    return out

def atomic_json(path, data):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    # OutFox reads files without shared-delete on some builds; a transient reader
    # must not lose a successfully accepted command.
    for attempt in range(30):
        try:
            os.replace(temp, path)
            return
        except PermissionError:
            if attempt == 29:
                raise
            time.sleep(0.01)

class Bridge:
    def __init__(self, root):
        self.directory = Path(root) / 'Save/GiftAPI'
        self.directory.mkdir(parents=True, exist_ok=True)
        config = self.directory / 'config.json'
        packaged_config = Path(__file__).with_name('config.json')
        if not config.exists() and packaged_config.exists():
            shutil.copyfile(packaged_config, config)
        gift_map=self.directory/'gift-map.json'
        if not gift_map.exists(): shutil.copy2(Path(__file__).with_name('gift-map.json'),gift_map)
        self.lock = threading.RLock()
        self.commands = []
        self.events = {}
        self.sequence = 0
        self.session = None
        self.server_id = str(uuid.uuid4())
        self.rejections = 0
        self._metric_key = None
        try:
            self.config = json.loads(config.read_text(encoding='utf-8-sig'))
        except (OSError, ValueError):
            self.config = {}
        saved=self.directory/'bridge-state.json'
        if saved.exists():
            state=json.loads(saved.read_text(encoding='utf-8-sig'))
            self.server_id=state['server_id'];self.sequence=state['sequence']
            self.commands=state['commands'];self.events=state['events']
        self.publish()

    def save_state(self):
        atomic_json(self.directory/'bridge-state.json',dict(server_id=self.server_id,sequence=self.sequence,commands=self.commands,events=self.events))

    def publish(self):
        # Anonymous heart receipts are short-lived; paid receipt IDs stay durable.
        free=[key for key,event in self.events.items() if event['request']['kind']=='hearts']
        for key in free[:-128]: self.events.pop(key,None)
        self.save_state()
        atomic_json(self.directory / 'commands.json', dict(server_id=self.server_id, commands=self.commands))

    def record(self, kind, payload):
        with self.lock:
            try:
                with (self.directory/'stream-metrics.jsonl').open('a', encoding='utf-8') as log:
                    log.write(json.dumps(dict(kind=kind, wall_time=time.time(), **payload), ensure_ascii=False)+'\n')
            except OSError:
                pass  # Recording cannot block gameplay or change gift outcomes.

    def status(self):
        path = self.directory / 'status.json'
        try:
            stat = path.stat()
            status = json.loads(path.read_text(encoding='utf-8-sig'))
            status['snapshot_age_seconds']=max(0,time.time()-stat.st_mtime)
            status['api_server_id'] = self.server_id
            status['connected'] = time.time() - stat.st_mtime <= 2.5
            if not status['connected'] and status.get('ready'):
                status.update(ready=False, reason='ITGmania gameplay heartbeat is stale')
            with self.lock:
                carry=status.get('carry_state')
                if status.get('server_id')==self.server_id and isinstance(carry,dict):
                    key=json.dumps(carry,sort_keys=True,ensure_ascii=False)
                    if key!=getattr(self,'_carry_key',None):
                        atomic_json(self.directory/'trial-state.json',carry)
                        self._carry_key=key
                receipts_changed=False
                if status.get('server_id') == self.server_id:
                    for result in status.get('results', []):
                        event = self.events.get(result.get('event_id'))
                        if event:
                            response = dict(result, session=event['response']['session'])
                            if response != event['response']:
                                self.record('result', response)
                                receipts_changed=True
                            event['response'] = response
                if receipts_changed:self.save_state()
                key = (status.get('session'), int(status.get('music_seconds', 0)),
                       status.get('ready'), status.get('bpm_offset'),status.get('pending_bpm_delta'),
                       (status.get('bpm_lock') or {}).get('event_id'), status.get('failed'))
                if key != self._metric_key and status.get('protocol_version') == 5:
                    fields = ['session','song_title','music_seconds','song_beat','base_bpm','effective_bpm',
                              'bpm_offset','bpm_delta','pending_bpm_delta','bpm_overflow','bpm_lock',
                              'note_remaining','lock_remaining','life','failed','ready','metrics',
                              'current_combo','max_combo','combo_breaks','judgments','trial_state']
                    self.record('status', {f: status.get(f) for f in fields})
                    self._metric_key = key
                status['api_rejections'] = self.rejections
            mapping=json.loads((self.directory/'gift-map.json').read_text(encoding='utf-8-sig'))
            status['gift_menu']=[dict(platform=platform,name=rule.get('name',gid),cost=rule.get('cost',0),image_url=rule.get('image_url',''),kind=rule['kind']) for platform,gifts in mapping.items() for gid,rule in gifts.items()]
            self._complete_status = (time.monotonic(), dict(status))
            return status
        except (OSError, ValueError):
            cached = getattr(self, '_complete_status', None)
            if cached and time.monotonic()-cached[0] < 0.3:
                return dict(cached[1])
            return {'ready': False, 'api_server_id': self.server_id, 'reason': 'Simply Love gameplay is not connected'}

    def submit(self, kind, body):
        command = validate(kind, body)
        with self.lock:
            previous = self.events.get(command['event_id'])
            if previous:
                if previous['request'] != command:
                    raise APIError(409, 'event_id already used with different parameters')
                return dict(previous['response'], duplicate=True)
            if len(self.events) >= 100000:
                raise APIError(503, 'Paid receipt history is full; archive bridge-state.json between streams')
            status = self.status()
            if status.get('connected') and status.get('protocol_version') not in (None,5):
                raise APIError(409,'Restart ITGmania to load GiftAPI version 5')
            active=bool(status.get('ready')) and status.get('protocol_version')==5
            if kind in ('notes','hearts') and not active:
                raise APIError(409,'Start a song with GiftAPI version 5')
            if kind=='notes' and command['player'] not in status.get('players',[]):
                raise APIError(409,'Requested player is not playing')
            session=status.get('session','') if kind in ('notes','hearts') else '*'
            seen=status.get('server_id')==self.server_id
            cursor=status.get('cursor',0) if seen else 0
            pending=[c for c in self.commands if c['sequence']>cursor]
            if kind=='notes':
                reserved=sum(c['count'] for c in pending if c['kind']=='notes')
                if command['count']>max(0,status.get('note_remaining',0)-reserved):
                    raise APIError(409,'NOTE ATTACK SOLD OUT or insufficient remaining slots')
            if len(pending) >= 128:
                raise APIError(429, 'Gameplay command queue is full')
            self.sequence += 1
            transport = dict(command, session=session, sequence=self.sequence)
            candidate = pending + [transport]
            self.commands = candidate
            response=dict(event_id=command['event_id'],state='submitted',session=session)
            self.events[command['event_id']]=dict(request=command,response=response)
            try:
                self.publish()
            except OSError:
                raise APIError(503, 'Could not publish command to ITGmania')
            self.record('accepted', dict(gift=command, session=session))
            return response

    def input(self,kind,body):
        if kind=='audience':
            if not isinstance(body,dict) or set(body)-{'tiktok','youtube'}: raise APIError(400,'Audience needs tiktok/youtube counts')
            value={p:numeric(body,p,0,10000000,integer=True) for p in ('tiktok','youtube')}
            atomic_json(self.directory/'audience.json',value)
            self.record('audience',value)
            return dict(state='updated',**value)
        if kind=='gift':
            if not isinstance(body,dict): raise APIError(400,'JSON object required')
            mapping=json.loads((self.directory/'gift-map.json').read_text(encoding='utf-8-sig'))
            rule=mapping.get(body.get('platform'),{}).get(body.get('gift_id'))
            if not rule: raise APIError(409,'Gift is not assigned in gift-map.json')
            count=numeric(dict(count=body.get('count',1)),'count',1,256,integer=True)
            command=dict(body);command.pop('count',None)
            if not isinstance(rule,dict) or rule.get('kind') not in ('notes','rescue','trial','lock'): raise APIError(400,'Invalid gift mapping')
            action=rule['kind']
            command['points' if action=='rescue' else 'count']=count*rule.get('points_per_unit' if action=='rescue' else 'units_per_gift',1)
            return self.submit(action,command)
        if kind=='hearts' and not self.status().get('ready'):
            command=validate(kind,body)
            if command['platform']=='tiktok': atomic_json(self.directory/'tiktok-baseline.json',command)
            return dict(state='ignored',reason='No active trial/gameplay')
        return self.submit(kind,body)

    def event(self, event_id):
        with self.lock:
            event = self.events.get(event_id)
            if not event:
                raise APIError(404, 'Unknown event_id')
            status = self.status()
            for result in status.get('results', []):
                if result.get('event_id') == event_id and status.get('server_id') == self.server_id:
                    event['response'] = dict(result, session=event['response']['session'])
            result = dict(event['response'])
            if event['request']['kind']=='notes' and result['state'] == 'submitted' and status.get('session') != result['session']:
                result.update(state='discarded', reason='Song ended or gameplay disconnected before acknowledgement')
            return result

def make_handler(bridge):
    class Handler(BaseHTTPRequestHandler):
        def reply(self, status, body):
            data = json.dumps(body, ensure_ascii=False, allow_nan=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            try:
                path = urlsplit(self.path).path
                if path in ('/overlay', '/overlay/', '/overlay/index.html'):
                    data = (Path(__file__).resolve().parent / 'overlay.html').read_bytes()
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html; charset=utf-8')
                    self.send_header('Content-Length', str(len(data)))
                    self.send_header('Cache-Control', 'no-store')
                    self.end_headers()
                    self.wfile.write(data)
                elif path == '/api/status':
                    self.reply(200, bridge.status())
                elif path == '/api/info':
                    self.reply(200, dict(api_version=5, server_id=bridge.server_id,
                                         runtime=str(bridge.directory.parent.parent.resolve())))
                elif path.startswith('/api/events/'):
                    self.reply(200, bridge.event(unquote(path[len('/api/events/'):])) )
                else:
                    raise APIError(404, 'Unknown endpoint')
            except APIError as e:
                self.reply(e.status, {'error': e.message})
            except OSError:
                self.reply(503, {'error': 'Overlay is unavailable'})

        def do_POST(self):
            try:
                path = urlsplit(self.path).path
                if path not in ('/api/notes','/api/tempo','/api/lock','/api/trial','/api/rescue','/api/hearts','/api/audience','/api/gift'):
                    raise APIError(404, 'Unknown endpoint')
                if self.headers.get('Transfer-Encoding'):
                    raise APIError(400, 'Use Content-Length, not Transfer-Encoding')
                try:
                    length = int(self.headers.get('Content-Length', '0'))
                except ValueError:
                    raise APIError(400, 'Invalid Content-Length')
                if not 0 < length <= 16384:
                    raise APIError(413, 'JSON request must be 1-16384 bytes')
                self.connection.settimeout(5)
                try:
                    body = json.loads(self.rfile.read(length).decode('utf-8'))
                except (ValueError, UnicodeError):
                    raise APIError(400, 'Invalid UTF-8 JSON')
                self.reply(202, bridge.input(path.rsplit('/',1)[-1],body))
            except APIError as e:
                bridge.rejections += 1
                bridge.record('rejected', dict(http_status=e.status, reason=e.message))
                self.reply(e.status, {'error': e.message})
            except (OSError, TimeoutError):
                self.reply(503, {'error': 'Request could not be processed'})

        def log_message(self, fmt, *args):
            print(fmt % args)
    return Handler

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--outfox', default=DEFAULT_ROOT)
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    # A local lock prevents two bridges from overwriting the same command file.
    import msvcrt
    lockfile = Path(args.outfox) / 'Save/GiftAPI/server.lock'
    lockfile.parent.mkdir(parents=True, exist_ok=True)
    with lockfile.open('a+b') as lock:
        lock.seek(0)
        if not lockfile.stat().st_size:
            lock.write(b'0'); lock.flush(); lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            raise SystemExit('Another GiftAPI bridge is already using this game folder')
        bridge = Bridge(args.outfox)
        def collect():
            while True:
                try: bridge.status()
                except (OSError,ValueError): pass
                time.sleep(.1)
        threading.Thread(target=collect,daemon=True,name='gameplay-checkpoint').start()
        server = ThreadingHTTPServer(('127.0.0.1', args.port), make_handler(bridge))
        print(f'ITGmania GiftAPI: http://127.0.0.1:{args.port}/api/status', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()

if __name__ == '__main__':
    main()
