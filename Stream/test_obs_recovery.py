import unittest
import obs_sync

class FakeOBS:
    def __init__(self, filters):
        self.filters = filters
        self.removed = []
    def call(self, request, data):
        if request == 'GetSourceFilterList':
            return dict(filters=self.filters)
        assert request == 'RemoveSourceFilter'
        self.removed.append(data['filterName'])

class RecoveryTests(unittest.TestCase):
    def test_removes_only_prior_controller_filters(self):
        current = 'ITGmania GiftAPI 表示連動 12345678'
        old = 'OutFox GiftAPI 表示連動 abcdef01'
        custom = 'My color correction'
        lookalike = 'OutFox GiftAPI 表示連動 notes'
        obs = FakeOBS([dict(filterName=n, filterKind='color_filter_v2')
                       for n in [current, old, custom, lookalike]])
        obs_sync.remove_stale_filters(obs, 'capture', current)
        self.assertEqual(obs.removed, [old])
    def test_preserves_other_filter_kinds(self):
        obs = FakeOBS([dict(filterName='OutFox GiftAPI 表示連動 abcdef01',
                            filterKind='crop_filter')])
        obs_sync.remove_stale_filters(obs, 'capture', 'current')
        self.assertEqual(obs.removed, [])

if __name__ == '__main__':
    unittest.main()
