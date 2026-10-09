"""Send occasional test gifts to the local OutFox API (Python 3.10+)."""
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
    parser = argparse.ArgumentParser(description='OutFoxにテスト用の矢印・速度ギフトを送ります。Ctrl+Cで終了。')
    parser.add_argument('--url', default='http://127.0.0.1:8765', help='APIのURL')
    parser.add_argument('--player', choices=['P1', 'P2'], default='P1')
    parser.add_argument('--notes-min', type=positive, default=3, help='矢印の最短送信間隔（秒）')
    parser.add_argument('--notes-max', type=positive, default=6, help='矢印の最長送信間隔（秒）')
    parser.add_argument('--tempo-min', type=positive, default=20, help='速度の最短送信間隔（秒）')
    parser.add_argument('--tempo-max', type=positive, default=30, help='速度の最長送信間隔（秒）')
    parser.add_argument('--tempo-duration', type=positive, default=30, help='各速度効果の持続時間（秒）')
    parser.add_argument('--run-seconds', type=positive, help='指定秒数で自動終了（通常は無制限）')
    args = parser.parse_args(argv)
    if args.notes_min > args.notes_max or args.tempo_min > args.tempo_max:
        parser.error('最短間隔は最長間隔以下にしてください')
    if not 0.05 <= args.tempo_duration <= 3600:
        parser.error('持続時間は0.05～3600秒にしてください')

    base = args.url.rstrip('/')
    deadline = time.monotonic() + args.run_seconds if args.run_seconds else math.inf
    session = None
    playing = False
    last_message = None
    next_notes = next_tempo = math.inf
    delta = 10
    log('テスト送信開始。APIとSimply Loveのプレイ開始を待ちます。Ctrl+Cで終了。')
    log(f'矢印: {args.notes_min:g}～{args.notes_max:g}秒ごとに1～3個 / 速度: '
        f'{args.tempo_min:g}～{args.tempo_max:g}秒ごとに+10/-10 BPMを交互に送信、各{args.tempo_duration:g}秒')
    try:
        while time.monotonic() < deadline:
            try:
                status = request_json(base + '/api/status')
                ready = bool(status.get('ready')) and args.player in status.get('players', [])
                if not ready:
                    message = '待機中: ' + status.get('reason', '対象プレイヤーのプレイ開始待ち')
                    playing = False
                else:
                    now = time.monotonic()
                    if not playing or session != status.get('session'):
                        session = status.get('session')
                        next_notes = now + random.uniform(args.notes_min, args.notes_max)
                        next_tempo = now + random.uniform(args.tempo_min, args.tempo_max)
                    playing = True
                    message = 'プレイを検出。テストギフトを送ります。'
                    if message != last_message:
                        log(message)
                        last_message = message
                    for kind, due in [('notes', next_notes), ('tempo', next_tempo)]:
                        if now < due:
                            continue
                        body = dict(event_id='test-' + str(uuid.uuid4()), player=args.player,
                                    sender=random.choice(['テスト視聴者A', 'テスト視聴者B', 'テスト視聴者C']))
                        if kind == 'notes':
                            body['count'] = random.randint(1, 3)
                            next_notes = now + random.uniform(args.notes_min, args.notes_max)
                            description = f'{body["sender"]}: 矢印{body["count"]}個'
                        else:
                            body.update(bpm_delta=delta, duration_seconds=args.tempo_duration)
                            next_tempo = now + random.uniform(args.tempo_min, args.tempo_max)
                            description = f'速度{delta:+d} BPM / {args.tempo_duration:g}秒'
                        result = request_json(base + '/api/' + kind, body)
                        log(f'送信受付: {description} ({result.get("state", "unknown")})')
                        if kind == 'tempo':
                            delta = -delta
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
            time.sleep(min(0.5, max(0, deadline - time.monotonic())))
    except KeyboardInterrupt:
        pass
    log('テスト送信終了。送信済みの速度効果は、それぞれの期限で終了します。')


if __name__ == '__main__':
    main()
