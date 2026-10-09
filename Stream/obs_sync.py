"""OutFox gameplay -> OBS scene-item visibility. Python 3.10+, no extra packages."""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import os
import re
from pathlib import Path
import socket
import struct
import time
import uuid
from urllib.request import urlopen

class OBSError(Exception):
    pass

def remove_stale_filters(obs, source_name, current_name):
    """Recover only filters created by this controller on an earlier run."""
    present = obs.call('GetSourceFilterList', dict(sourceName=source_name))['filters']
    for f in present:
        name = f['filterName']
        if (name != current_name and f['filterKind'] == 'color_filter_v2'
                and re.fullmatch(r'(?:OutFox|ITGmania) GiftAPI 表示連動 [0-9a-f]{8}', name)):
            obs.call('RemoveSourceFilter', dict(sourceName=source_name, filterName=name))

def controller_lock(host, port):
    """Windows releases this mutex even when the terminal is forcibly closed."""
    if os.name != 'nt':
        return None
    import ctypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
    kernel.CreateMutexW.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    key = hashlib.sha256(f'{host}:{port}'.encode()).hexdigest()[:24]
    handle = kernel.CreateMutexW(None, False, 'Local\\SimplyLoveGiftAPI_OBS_'+key)
    error = ctypes.get_last_error()
    if not handle:
        raise OBSError('OBS表示連動の起動ロックを取得できません')
    if error == 183:
        kernel.CloseHandle(handle)
        raise OBSError('OBS表示連動は既に起動しています')
    return kernel, handle

class OBSWebSocket:
    """Small synchronous RFC6455 client for the OBS v5 request protocol."""
    def __init__(self, host, port, password=''):
        self.socket = socket.create_connection((host, port), timeout=2)
        self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.socket.settimeout(2)
        self.buffer = b''
        self.sequence = 0
        try:
            key = base64.b64encode(os.urandom(16)).decode()
            self.socket.sendall((f'GET / HTTP/1.1\r\nHost: {host}:{port}\r\nUpgrade: websocket\r\n'
                                 f'Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n').encode())
            while b'\r\n\r\n' not in self.buffer:
                chunk = self.socket.recv(4096)
                if not chunk: raise OBSError('OBSとの接続が切れました')
                self.buffer += chunk
                if len(self.buffer) > 65536: raise OBSError('WebSocket応答が不正です')
            headers, self.buffer = self.buffer.split(b'\r\n\r\n', 1)
            lines = headers.decode('ascii').split('\r\n')
            fields = {name.lower(): value for name, value in
                      (line.split(':', 1) for line in lines[1:] if ':' in line)}
            expected = base64.b64encode(hashlib.sha1((key+'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest()).decode()
            if ' 101 ' not in lines[0] or fields.get('sec-websocket-accept', '').strip() != expected:
                raise OBSError('OBS WebSocket v5に接続できません')
            hello = self.receive()
            if hello.get('op') != 0: raise OBSError('OBS WebSocket v5のHelloがありません')
            identify = dict(rpcVersion=1, eventSubscriptions=0)
            auth = hello['d'].get('authentication')
            if auth:
                secret = base64.b64encode(hashlib.sha256((password+auth['salt']).encode()).digest()).decode()
                identify['authentication'] = base64.b64encode(hashlib.sha256((secret+auth['challenge']).encode()).digest()).decode()
            self.send(dict(op=1, d=identify))
            if self.receive().get('op') != 2: raise OBSError('OBSの認証に失敗しました')
        except BaseException:
            self.close()
            raise

    def exact(self, size):
        while len(self.buffer) < size:
            chunk = self.socket.recv(max(4096, size-len(self.buffer)))
            if not chunk: raise OBSError('OBSとの接続が切れました')
            self.buffer += chunk
        result, self.buffer = self.buffer[:size], self.buffer[size:]
        return result

    def frame(self, opcode, payload):
        mask = os.urandom(4)
        size = len(payload)
        length = (bytes([size|128]) if size < 126 else bytes([126|128])+struct.pack('!H', size)
                  if size <= 65535 else bytes([127|128])+struct.pack('!Q', size))
        masked = bytes(value ^ mask[i%4] for i, value in enumerate(payload))
        self.socket.sendall(bytes([128|opcode])+length+mask+masked)

    def send(self, message):
        self.frame(1, json.dumps(message, ensure_ascii=False).encode('utf-8'))

    def receive(self):
        parts = bytearray()
        while True:
            first, second = self.exact(2)
            opcode, final = first & 15, bool(first & 128)
            size = second & 127
            if size == 126: size = struct.unpack('!H', self.exact(2))[0]
            elif size == 127: size = struct.unpack('!Q', self.exact(8))[0]
            if size > 8*1024*1024: raise OBSError('OBS応答が大きすぎます')
            mask = self.exact(4) if second & 128 else None
            payload = self.exact(size)
            if mask: payload = bytes(value ^ mask[i%4] for i, value in enumerate(payload))
            if opcode == 8: raise OBSError('OBSとの接続が閉じられました（認証・サーバー設定を確認）')
            if opcode == 9: self.frame(10, payload); continue
            if opcode == 10: continue
            if opcode not in (0, 1): raise OBSError('OBSから予期しない応答がありました')
            parts.extend(payload)
            if len(parts) > 8*1024*1024: raise OBSError('OBS応答が大きすぎます')
            if final: return json.loads(parts.decode('utf-8'))

    def call(self, kind, data=None):
        self.sequence += 1
        rid = str(self.sequence)
        self.send(dict(op=6, d=dict(requestType=kind, requestId=rid, requestData=data or {})))
        while True:
            message = self.receive()
            if message.get('op') == 7 and message['d'].get('requestId') == rid:
                result = message['d']
                if not result['requestStatus']['result']:
                    raise OBSError(f'OBS操作失敗: {kind} ({result["requestStatus"].get("code")})')
                return result.get('responseData', {})

    def close(self):
        try: self.socket.close()
        except OSError: pass


def log(message):
    print(f'[{time.strftime("%H:%M:%S")}] {message}', flush=True)


def settings(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def target_items(obs, source_name, scene_name=None):
    inputs = obs.call('GetInputList', dict(inputKind='game_capture'))['inputs']
    names = [item['inputName'] for item in inputs]
    if source_name:
        if source_name not in names: raise OBSError('指定したゲームキャプチャソースが見つかりません')
        name = source_name
    elif len(names) == 1:
        name = names[0]
    else:
        raise OBSError('ゲームキャプチャが0個または複数あります。--sourceで対象の名前を指定してください')
    root = scene_name or obs.call('GetCurrentProgramScene')['currentProgramSceneName']
    found = []
    visited = set()
    def walk(owner, group=False):
        key = (owner, group)
        if key in visited: return
        visited.add(key)
        items = obs.call('GetGroupSceneItemList' if group else 'GetSceneItemList', dict(sceneName=owner))['sceneItems']
        for item in items:
            if item['sourceName'] == name:
                found.append(dict(owner=owner, group=group, id=item['sceneItemId'], name=name, enabled=item['sceneItemEnabled']))
            elif item.get('isGroup'):
                walk(item['sourceName'], True)
            elif item.get('sourceType') == 'OBS_SOURCE_TYPE_SCENE':
                walk(item['sourceName'])
    walk(root)
    if not found: raise OBSError('対象ソースが現在のシーンにありません（必要なら--sceneで指定）')
    return found


def main(argv=None):
    default_config = Path(os.environ.get('APPDATA', ''))/'obs-studio/plugin_config/obs-websocket/config.json'
    parser = argparse.ArgumentParser(description='プレイ中だけOBSゲームキャプチャを表示します。')
    parser.add_argument('--api-url', default='http://127.0.0.1:8765')
    parser.add_argument('--obs-config', default=str(default_config), help='OBS WebSocket設定ファイル。パスワードは自動読込')
    parser.add_argument('--obs-host', default='127.0.0.1')
    parser.add_argument('--obs-port', type=int)
    parser.add_argument('--source', help='ゲームキャプチャのソース名（1個なら自動選択）')
    parser.add_argument('--scene', help='対象シーン名（通常は現在の配信シーン）')
    parser.add_argument('--interval', type=float, default=0.1)
    parser.add_argument('--run-seconds', type=float)
    args = parser.parse_args(argv)
    if not 0.05 <= args.interval <= 10: parser.error('確認間隔は0.05～10秒にしてください')
    if args.run_seconds is not None and not 0 < args.run_seconds < float('inf'): parser.error('実行秒数は正の有限値にしてください')
    if args.obs_port is not None and not 1 <= args.obs_port <= 65535: parser.error('ポートは1～65535にしてください')
    deadline = time.monotonic()+args.run_seconds if args.run_seconds else float('inf')
    config = settings(args.obs_config)
    try:
        lock = controller_lock(args.obs_host, args.obs_port or config.get('server_port',4455))
    except OBSError as error:
        log(str(error))
        return
    obs = None
    original = {}
    filter_name = 'ITGmania GiftAPI 表示連動 '+uuid.uuid4().hex[:8]
    filters = set()
    filter_state = {}
    last_message = None
    def announce(message):
        nonlocal last_message
        if message != last_message: log(message); last_message = message
    log('OBS表示連動開始。Ctrl+Cで終了し、ソースを開始前の表示状態へ戻します。')
    try:
        while time.monotonic() < deadline:
            poll_started = time.monotonic()
            try:
                if obs is None:
                    config = settings(args.obs_config)
                    if not config.get('server_enabled') and args.obs_port is None:
                        raise OBSError('OBSの「ツール → WebSocketサーバー設定」でサーバーを有効にして適用してください')
                    obs = OBSWebSocket(args.obs_host, args.obs_port or config.get('server_port', 4455), config.get('server_password', ''))
                    filter_state.clear()
                try:
                    with urlopen(args.api_url.rstrip('/')+'/api/status', timeout=1) as response: status = json.load(response)
                    playing = bool(status.get('ready'))
                    reason = 'プレイ中' if playing else '選曲中・終了・ポーズなど'
                except (OSError, ValueError):
                    playing, reason = False, 'OutFox API未接続（start-api.cmdを確認）'
                items = target_items(obs, args.source, args.scene)
                name = items[0]['name']
                if name not in filter_state:
                    remove_stale_filters(obs, name, filter_name)
                    present = obs.call('GetSourceFilterList', dict(sourceName=name))['filters']
                    if not any(f['filterName'] == filter_name for f in present):
                        obs.call('CreateSourceFilter', dict(sourceName=name, filterName=filter_name,
                                 filterKind='color_filter_v2', filterSettings=dict(opacity=0.0)))
                    filters.add(name)
                if filter_state.get(name) != playing:
                    obs.call('SetSourceFilterSettings', dict(sourceName=name, filterName=filter_name,
                             filterSettings=dict(opacity=1.0 if playing else 0.0), overlay=True))
                    filter_state[name] = playing
                for item in items:
                    key = (item['owner'], item['id'], item['name'])
                    original.setdefault(key, item.copy())
                    # Keep capture active even while transparent: hiding the item
                    # stops OBS's game hook and delays the next capture startup.
                    if not item['enabled']:
                        obs.call('SetSceneItemEnabled', dict(sceneName=item['owner'], sceneItemId=item['id'], sceneItemEnabled=True))
                announce(('表示' if playing else '非表示')+': '+items[0]['name']+' / '+reason)
            except (OSError, ValueError, KeyError, OBSError) as error:
                if obs is not None: obs.close(); obs = None
                # Do not print credentials or raw protocol frames.
                announce('待機中: '+(str(error) if isinstance(error, OBSError) else 'OBS接続・設定を確認してください'))
            time.sleep(min(max(0, args.interval-(time.monotonic()-poll_started)),
                           max(0, deadline-time.monotonic())))
    except KeyboardInterrupt:
        pass
    finally:
        if original and obs is None:
            try:
                config = settings(args.obs_config)
                obs = OBSWebSocket(args.obs_host, args.obs_port or config.get('server_port',4455), config.get('server_password',''))
            except (OSError, ValueError, KeyError, OBSError): pass
        restored = 0
        if obs:
            for item in original.values():
                try:
                    method = 'GetGroupSceneItemList' if item['group'] else 'GetSceneItemList'
                    present = obs.call(method, dict(sceneName=item['owner']))['sceneItems']
                    if any(i['sceneItemId']==item['id'] and i['sourceName']==item['name'] for i in present):
                        obs.call('SetSceneItemEnabled', dict(sceneName=item['owner'],sceneItemId=item['id'],sceneItemEnabled=item['enabled']))
                        restored += 1
                except (OSError, ValueError, KeyError, OBSError):
                    log('OBSに接続できず表示状態を戻せませんでした。ソースの目のアイコンを確認してください。')
                    break
            for name in filters:
                try:
                    obs.call('RemoveSourceFilter', dict(sourceName=name, filterName=filter_name))
                except (OSError, ValueError, KeyError, OBSError):
                    log('連動用フィルターを削除できませんでした。OBSのフィルターにある「'+filter_name+'」を削除してください。')
            obs.close()
        elif filters:
            log('OBSのフィルターにある「'+filter_name+'」を削除してください。')
        if original and not restored: log('元の表示状態へ戻せませんでした。OBSの目のアイコンを確認してください。')
        log('OBS表示連動終了。')
        if lock:
            lock[0].CloseHandle(lock[1])

if __name__ == '__main__':
    main()
