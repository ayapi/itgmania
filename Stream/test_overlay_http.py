"""Check that the OBS page and live effect metadata share one local origin."""
import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import urlopen
import bridge


class OverlayTests(unittest.TestCase):
    def test_overlay_and_effect_status(self):
        with tempfile.TemporaryDirectory() as folder:
            api = bridge.Bridge(Path(folder))
            payload = dict(ready=True, server_id=api.server_id, song_title='曲名',
                           song_artist='アーティスト', effective_bpm=150,
                           active_tempo_effects=[dict(sender='<b>視聴者</b>', bpm_delta=10,
                                                     remaining_seconds=8)])
            (api.directory/'status.json').write_text(json.dumps(payload), encoding='utf-8')
            server = bridge.ThreadingHTTPServer(('127.0.0.1', 0), bridge.make_handler(api))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                origin = 'http://127.0.0.1:' + str(server.server_port)
                with urlopen(origin+'/overlay') as response:
                    self.assertEqual(response.headers.get_content_type(), 'text/html')
                    html = response.read().decode('utf-8')
                    self.assertIn("fetch('/api/status'", html)
                    self.assertIn('name.textContent=effect.sender', html)
                with urlopen(origin+'/api/status') as response:
                    status = json.load(response)
                self.assertTrue(status['connected'])
                self.assertEqual(status['song_artist'], 'アーティスト')
                self.assertEqual(status['active_tempo_effects'], payload['active_tempo_effects'])
            finally:
                server.shutdown()
                server.server_close()
                thread.join()


if __name__ == '__main__':
    unittest.main()
