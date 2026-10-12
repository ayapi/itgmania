"""Send note gifts, random small BPM changes, occasional big gifts and locks."""
from __future__ import annotations

import argparse
import json
import math
import random
import time
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def request_json(url, body=None):
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode('utf-8')
    request = Request(url, data=data, headers={'Content-Type': 'application/json'})
    with urlopen(request, timeout=2) as response:
        return json.load(response)


def log(message):
    print(f'[{time.strftime("%H:%M:%S")}] {message}', flush=True)


def positive(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError('正の数を指定してください')
    return number


def main(argv=None):
    parser = argparse.ArgumentParser(description='ITGmaniaにテスト用の矢印・BPM・ロックギフトを送ります。Ctrl+Cで終了。')
    parser.add_argument('--url', default='http://127.0.0.1:8765', help='APIのURL')
    parser.add_argument('--player', choices=['P1', 'P2'], default='P1')
    parser.add_argument('--notes-min', type=positive, default=3, help='矢印の最短送信間隔（秒）')
    parser.add_argument('--notes-max', type=positive, default=6, help='矢印の最長送信間隔（秒）')
    parser.add_argument('--tempo-min', type=positive, default=20, help='±10 BPMの最短送信間隔（秒）')
    parser.add_argument('--tempo-max', type=positive, default=30, help='±10 BPMの最長送信間隔（秒）')
    parser.add_argument('--small-tempo-min', type=positive, default=3, help='±1 BPMの最短送信間隔（秒）')
    parser.add_argument('--small-tempo-max', type=positive, default=10, help='±1 BPMの最長送信間隔（秒）')
    parser.add_argument('--lock-min', type=positive, default=35, help='ロックの最短送信間隔（秒）')
    parser.add_argument('--lock-max', type=positive, default=55, help='ロックの最長送信間隔（秒）')
    parser.add_argument('--tempo-duration', type=positive, default=30, help='互換引数（Version 3では無視）')
    parser.add_argument('--run-seconds', type=positive, help='指定秒数で自動終了（通常は無制限）')
    args = parser.parse_args(argv)
    if any(low > high for low, high in [(args.notes_min,args.notes_max),
                                        (args.tempo_min,args.tempo_max),
                                        (args.small_tempo_min,args.small_tempo_max),
                                        (args.lock_min,args.lock_max)]):
        parser.error('最短間隔は最長間隔以下にしてください')
    if not 0.05 <= args.tempo_duration <= 3600:
        parser.error('持続時間は0.05～3600秒にしてください')

    base = args.url.rstrip('/')
    deadline = time.monotonic() + args.run_seconds if args.run_seconds else math.inf
    session = None
    playing = False
    last_message = None
    next_notes = next_tempo = next_small = next_lock = math.inf
    delta = 10
    log('テスト送信開始。APIとSimply Loveのプレイ開始を待ちます。Ctrl+Cで終了。')
    log(f'矢印: {args.notes_min:g}～{args.notes_max:g}秒ごとに1～3個 / 速度: '
        f'±1 BPM: {args.small_tempo_min:g}～{args.small_tempo_max:g}秒ごと、+1/-1を各50%で送信 / '
        f'±10 BPM: {args.tempo_min:g}～{args.tempo_max:g}秒ごとに交互 / '
        f'ロック: {args.lock_min:g}～{args.lock_max:g}秒ごと（累積、4小節ごとに減衰）')
    try:
        while time.monotonic() < deadline:
            try:
                status = request_json(base + '/api/status')
                ready = (bool(status.get('ready')) and args.player in status.get('players', [])
                         and status.get('protocol_version') == 3)
                if not ready:
                    message = '待機中: ' + status.get('reason', '対象プレイヤーのプレイ開始待ち')
                    playing = False
                else:
                    now = time.monotonic()
                    if not playing or session != status.get('session'):
                        session = status.get('session')
                        next_notes = now + random.uniform(args.notes_min, args.notes_max)
                        next_tempo = now + random.uniform(args.tempo_min, args.tempo_max)
                        next_small = now + random.uniform(args.small_tempo_min, args.small_tempo_max)
                        next_lock = now + random.uniform(args.lock_min, args.lock_max)
                        delta = 10
                    playing = True
                    message = 'プレイを検出。テストギフトを送ります。'
                    if message != last_message:
                        log(message)
                        last_message = message
                    for action, due in [('notes', next_notes), ('small', next_small),
                                        ('tempo', next_tempo), ('lock', next_lock)]:
                        if now < due:
                            continue
                        body = dict(event_id='test-' + str(uuid.uuid4()), player=args.player,
                                    sender=random.choice(['テスト視聴者A', 'テスト視聴者B', 'テスト視聴者C']))
                        kind = 'tempo' if action == 'small' else action
                        if action == 'notes':
                            next_notes = now + random.uniform(args.notes_min, args.notes_max)
                            remaining = int(status.get('note_remaining', 0))
                            if remaining <= 0:
                                continue
                            body['count'] = random.randint(1, min(3, remaining))
                            description = f'{body["sender"]}: 矢印{body["count"]}個'
                        elif action == 'small':
                            body['bpm_delta'] = random.choice([-1, 1])
                            next_small = now + random.uniform(args.small_tempo_min, args.small_tempo_max)
                            description = f'{body["sender"]}: {body["bpm_delta"]:+d} BPM'
                        elif action == 'tempo':
                            body.update(bpm_delta=delta)
                            next_tempo = now + random.uniform(args.tempo_min, args.tempo_max)
                            description = f'{body["sender"]}: {delta:+d} BPM'
                            delta = -delta
                        else:
                            next_lock = now + random.uniform(args.lock_min, args.lock_max)
                            if int(status.get('lock_remaining', 0)) <= 0:
                                continue
                            body['measures'] = status.get('lock_min_measures', 4)
                            description = f'{body["sender"]}: BPMロック {body["measures"]}小節'
                        try:
                            result = request_json(base + '/api/' + kind, body)
                        except HTTPError as error:
                            try:
                                reason = json.load(error).get('error', str(error))
                            except (OSError, ValueError):
                                reason = str(error)
                            log(f'送信拒否: {description} — {reason}')
                            # A sold-out/limited gift must not reset the other
                            # schedules, otherwise frequent +1s starve locks.
                            continue
                        log(f'送信受付: {description} ({result.get("state", "unknown")})')
                if message != last_message:
                    log(message)
                    last_message = message
            except (URLError, TimeoutError, OSError, ValueError) as error:
                # A song may end between GET and POST. Do not retry a potentially
                # accepted gift, or build a backlog while gameplay is unavailable.
                playing = False
                message = (f'待機中: API応答 {error.code}' if isinstance(error, HTTPError)
                           else '待機中: APIに接続できません。start-api.cmdの起動を確認してください。')
                if message != last_message:
                    log(message)
                    last_message = message
            time.sleep(min(0.1, max(0, deadline - time.monotonic())))
    except KeyboardInterrupt:
        pass
    log('テスト送信終了。BPMオフセットは減衰し、次の曲で0になります。')


if __name__ == '__main__':
    main()
