import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import urlopen,Request
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
from overlay_server import DisplayState,handler
from prepare_platform_overlays import build

class LanOverlayTests(unittest.TestCase):
    def test_public_snapshot_aging_and_fields(self):
        state=DisplayState();state.update(dict(ready=True,connected=True,song_beat=30,snapshot_age_seconds=.1,
            server_id='private',carry_state={'tokens':['private']},results=['private']),10)
        view=state.get(10.4)
        self.assertAlmostEqual(view['snapshot_age_seconds'],.5)
        self.assertEqual(view['song_beat'],30)
        self.assertNotIn('carry_state',view);self.assertNotIn('results',view);self.assertNotIn('server_id',view)
        self.assertFalse(state.get(12)['ready'])
    def test_separate_html_and_read_only_routes(self):
        source=Path(__file__).resolve().parent;build(source)
        state=DisplayState();state.update(dict(protocol_version=5,ready=True,gift_menu=[]))
        server=ThreadingHTTPServer(('127.0.0.1',0),handler(source,state,source.parent))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        origin=f'http://127.0.0.1:{server.server_port}'
        try:
            for platform in ('tiktok','youtube'):
                with urlopen(origin+'/'+platform) as r:html=r.read().decode()
                self.assertIn(f'<meta name="stream-platform" content="{platform}">',html)
                self.assertIn("fetch('/api/status'",html)
                self.assertEqual(html,(source/f'overlay-{platform}.html').read_bytes().decode('utf-8'))
            with urlopen(origin+'/light') as r:self.assertIn('stream-mode" content="light',r.read().decode())
            with urlopen(origin+'/api/status') as r:self.assertTrue(json.load(r)['ready'])
            for path in ('/api/info','/api/events/secret','/../bridge.py'):
                with self.assertRaises(HTTPError) as error:urlopen(origin+path)
                self.assertEqual(error.exception.code,404)
            with self.assertRaises(HTTPError) as error:urlopen(Request(origin+'/api/trial',data=b'{}'))
            self.assertEqual(error.exception.code,405)
        finally:server.shutdown();server.server_close();thread.join()
if __name__=='__main__':unittest.main()
