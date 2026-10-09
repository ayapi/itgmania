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
    allowed = {'event_id', 'sender', 'player'} | ({'count'} if kind == 'notes' else {'bpm_delta', 'duration_seconds'})
    if set(body) - allowed:
        raise APIError(400, 'Unknown fields: ' + ', '.join(sorted(set(body) - allowed)))
    sender = body.get('sender', '')
    if not isinstance(sender, str) or len(sender) > 80 or any(ord(c) < 32 for c in sender):
        raise APIError(400, 'sender must be a name of up to 80 characters without control characters')
    if kind == 'notes' and not sender:
        raise APIError(400, 'sender is required for notes')
    player = body.get('player', 'P1')
    if player not in ('P1', 'P2'):
        raise APIError(400, 'player must be P1 or P2')
    event_id = body.get('event_id', str(uuid.uuid4()))
    if not isinstance(event_id, str) or not 1 <= len(event_id) <= 128 or any(ord(c) < 32 for c in event_id):
        raise APIError(400, 'event_id must be a string of 1-128 characters')
    out = dict(kind=kind, event_id=event_id, sender=sender, player=player)
    if kind == 'notes':
        out['count'] = numeric(body, 'count', 1, 256, integer=True)
    else:
        out['bpm_delta'] = numeric(body, 'bpm_delta', -1000, 1000)
        out['duration_seconds'] = numeric(body, 'duration_seconds', 0.05, 3600)
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
        self.lock = threading.RLock()
        self.commands = []
        self.events = {}
        self.sequence = 0
        self.session = None
        self.server_id = str(uuid.uuid4())
        self.publish()

    def publish(self):
        atomic_json(self.directory / 'commands.json', dict(server_id=self.server_id, commands=self.commands))

    def status(self):
        path = self.directory / 'status.json'
        try:
            stat = path.stat()
            status = json.loads(path.read_text(encoding='utf-8-sig'))
            status['connected'] = time.time() - stat.st_mtime <= 2.5
            if not status['connected'] and status.get('ready'):
                status.update(ready=False, reason='OutFox gameplay heartbeat is stale')
            with self.lock:
                if status.get('server_id') == self.server_id:
                    for result in status.get('results', []):
                        event = self.events.get(result.get('event_id'))
                        if event:
                            event['response'] = dict(result, session=event['response']['session'])
            return status
        except (OSError, ValueError):
            return {'ready': False, 'reason': 'Simply Love gameplay is not connected'}

    def submit(self, kind, body):
        command = validate(kind, body)
        with self.lock:
            previous = self.events.get(command['event_id'])
            if previous:
                if previous['request'] != command:
                    raise APIError(409, 'event_id already used with different parameters')
                return dict(previous['response'], duplicate=True)
            if len(self.events) >= 10000:
                raise APIError(503, 'Event history is full; restart the bridge between streams')
            status = self.status()
            if not status.get('ready'):
                raise APIError(409, status.get('reason', 'Not playing a song'))
            if command['player'] not in status.get('players', []):
                raise APIError(409, 'Requested player is not playing')
            session = status['session']
            if session != self.session:
                self.session = session
                self.commands = []
            seen = status.get('server_id') == self.server_id
            cursor = status.get('cursor', 0) if seen else 0
            pending = [c for c in self.commands if c['sequence'] > cursor]
            if len(pending) >= 128:
                raise APIError(429, 'Gameplay command queue is full')
            self.sequence += 1
            transport = dict(command, session=session, sequence=self.sequence)
            candidate = pending + [transport]
            old = self.commands
            self.commands = candidate
            try:
                self.publish()
            except OSError:
                self.commands = old
                raise APIError(503, 'Could not publish command to OutFox')
            response = dict(event_id=command['event_id'], state='submitted', session=session)
            self.events[command['event_id']] = dict(request=command, response=response)
            return response

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
            if result['state'] == 'submitted' and status.get('session') != result['session']:
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
                if path == '/api/status':
                    self.reply(200, bridge.status())
                elif path.startswith('/api/events/'):
                    self.reply(200, bridge.event(unquote(path[len('/api/events/'):])) )
                else:
                    raise APIError(404, 'Unknown endpoint')
            except APIError as e:
                self.reply(e.status, {'error': e.message})

        def do_POST(self):
            try:
                path = urlsplit(self.path).path
                if path not in ('/api/notes', '/api/tempo'):
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
                self.reply(202, bridge.submit(path.rsplit('/', 1)[-1], body))
            except APIError as e:
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
