"""Validate bounded reservations, duplicate delivery and the v3 API boundary."""
import json
from pathlib import Path
import tempfile
import unittest
from bridge import APIError, Bridge, validate


class Version3Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.api = Bridge(Path(self.temp.name))
        self.status = dict(protocol_version=3, ready=True, session='song', players=['P1'],
                           server_id=self.api.server_id, cursor=0, note_remaining=3,
                           lock_remaining=2, lock_min_measures=4, bpm_offset=0,
                           pending_bpm_delta=0, bpm_stored_limit=50)
        self.write()

    def tearDown(self):
        self.temp.cleanup()

    def write(self):
        (self.api.directory/'status.json').write_text(json.dumps(self.status), encoding='utf-8')

    def test_tempo_integer_and_legacy_duration(self):
        self.assertEqual(validate('tempo', dict(bpm_delta=1, duration_seconds=30))['bpm_delta'], 1)
        self.assertNotIn('duration_seconds', validate('tempo', dict(bpm_delta=1)))
        for delta in (1.5, 0, True):
            with self.assertRaises(APIError):
                validate('tempo', dict(bpm_delta=delta))

    def test_note_reservations_and_idempotency(self):
        body = dict(event_id='n', sender='A', count=2)
        self.api.submit('notes', body)
        self.assertTrue(self.api.submit('notes', body)['duplicate'])
        with self.assertRaises(APIError):
            self.api.submit('notes', dict(sender='B', count=2))
        self.api.submit('notes', dict(sender='B', count=1))

    def test_lock_reservations_and_block_size(self):
        self.api.submit('lock', dict(sender='A', measures=8))
        for measures in (4, 3):
            with self.assertRaises(APIError):
                self.api.submit('lock', dict(sender='B', measures=measures))

    def test_offset_reservations(self):
        self.api.submit('tempo', dict(sender='A', bpm_delta=40))
        with self.assertRaises(APIError):
            self.api.submit('tempo', dict(sender='B', bpm_delta=11))
        self.api.submit('tempo', dict(sender='B', bpm_delta=-10))
        self.api.submit('tempo', dict(sender='B', bpm_delta=20))

    def test_reducing_overflow_after_chart_bpm_change(self):
        self.status.update(bpm_offset=60, bpm_stored_limit=50)
        self.write()
        self.api.submit('tempo', dict(sender='救済', bpm_delta=-1))
        with self.assertRaises(APIError):
            self.api.submit('tempo', dict(sender='攻撃', bpm_delta=2))

    def test_old_gameplay_cannot_receive_new_protocol(self):
        self.status.pop('protocol_version')
        self.write()
        with self.assertRaises(APIError):
            self.api.submit('tempo', dict(sender='A', bpm_delta=1))

    def test_held_receipt_completes_even_between_result_pages(self):
        self.api.submit('tempo', dict(event_id='t', sender='A', bpm_delta=1))
        self.status.update(cursor=1, results=[dict(event_id='t', state='held', lock_event_id='l')])
        self.write()
        self.assertEqual(self.api.event('t')['state'], 'held')
        self.status.update(results=[], completed_locks=['l'])
        self.write()
        self.assertEqual(self.api.event('t')['state'], 'applied')


if __name__ == '__main__':
    unittest.main()
