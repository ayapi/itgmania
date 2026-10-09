import json, tempfile, unittest, time
from pathlib import Path
from unittest.mock import patch
import bridge

class HeartbeatTests(unittest.TestCase):
    def test_partial_write_retains_recent_complete_status_then_expires(self):
        with tempfile.TemporaryDirectory() as folder:
            api=bridge.Bridge(Path(folder))
            status=api.directory/'status.json'
            status.write_text(json.dumps(dict(ready=True, server_id=api.server_id)),encoding='utf-8')
            self.assertTrue(api.status()['ready'])
            status.write_text('{"ready":',encoding='utf-8')
            self.assertTrue(api.status()['ready'])
            with patch.object(bridge.time,'monotonic',return_value=time.monotonic()+1):
                self.assertFalse(api.status()['ready'])

if __name__=='__main__':unittest.main()
