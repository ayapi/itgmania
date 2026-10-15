import tempfile,unittest
from pathlib import Path
from stream_results import install


class ResultsInstallTests(unittest.TestCase):
    def test_installs_once_and_guards_normal_theme(self):
        with tempfile.TemporaryDirectory() as folder:
            theme=Path(folder)/'Themes/Simply Love/BGAnimations'
            common=theme/'ScreenEvaluation common'
            common.mkdir(parents=True)
            (common/'default.lua').write_text('local t = Def.ActorFrame{Name="ScreenEval Common"}\nreturn t')
            (theme/'ScreenEvaluationStage in').mkdir()
            for name in ['ScreenEvaluationStage background.lua','ScreenEvaluationStage in/default.lua']:
                (theme/name).write_text('return Def.ActorFrame{}')
            install(folder)
            first=(common/'default.lua').read_text()
            install(folder)
            self.assertEqual(first,(common/'default.lua').read_text())
            self.assertEqual(first.count('StreamCompactEvaluation'),1)
            self.assertIn('local result=LoadActor',first)
            self.assertTrue((common/'StreamEvaluation.lua').is_file())
            self.assertTrue((common/'default.lua.before-stream-results').is_file())
            self.assertIn('StreamerMode',(theme/'ScreenEvaluationStage background.lua').read_text())


if __name__=='__main__':unittest.main()
