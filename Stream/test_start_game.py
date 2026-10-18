"""Prevent competing portable games from publishing OBS state."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

if sys.platform == 'win32':
    import start_game as game


@unittest.skipUnless(sys.platform == 'win32', 'Windows launcher')
class LaunchTests(unittest.TestCase):
    def test_existing_game_is_reused_without_spawning(self):
        with patch.object(game.kernel, 'CreateMutexW', return_value=123), \
             patch.object(game.kernel, 'CloseHandle'), \
             patch.object(game, 'running_game', return_value=456), \
             patch.object(game.subprocess, 'Popen') as spawn:
            self.assertEqual(game.launch_or_reuse(Path('.')), 456)
            spawn.assert_not_called()

    def test_concurrent_click_does_not_spawn(self):
        with patch.object(game.kernel, 'CreateMutexW', return_value=123), \
             patch.object(game.kernel, 'CloseHandle'), \
             patch.object(game.ctypes, 'get_last_error', return_value=183), \
             patch.object(game, 'running_game', return_value=None), \
             patch.object(game.subprocess, 'Popen') as spawn:
            self.assertIsNone(game.launch_or_reuse(Path('.')))
            spawn.assert_not_called()

    def test_new_launch_disables_engine_duplicates(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'Save').mkdir()
            prefs=root/'Save/Preferences.ini'
            for content in ('[Options]\nAllowMultipleInstances=1\nSoundVolume=0.5\n',
                            '[Options]\nSoundVolume=0.5\n'):
                prefs.write_text(content, encoding='utf-8')
                process=Mock(pid=789)
                process.poll.return_value=None
                with patch.object(game.kernel, 'CreateMutexW', return_value=123), \
                     patch.object(game.kernel, 'CloseHandle'), \
                     patch.object(game.ctypes, 'get_last_error', return_value=0), \
                     patch.object(game, 'running_game', return_value=None), \
                     patch.object(game, 'find_window', return_value=1), \
                     patch.object(game.subprocess, 'Popen', return_value=process) as spawn:
                    self.assertEqual(game.launch_or_reuse(root), 789)
                    spawn.assert_called_once_with([str(root/'Program/ITGmania.exe')], cwd=root)
                text=prefs.read_text(encoding='utf-8')
                self.assertIn('AllowMultipleInstances=0\n',text)
                self.assertIn('SoundVolume=0.5\n',text)


if __name__ == '__main__':
    unittest.main()
