"""Place judgment above receptors and combo immediately below them."""
from pathlib import Path


def install(root):
    path=Path(root)/'Themes/Simply Love/Scripts/SL-Layout.lua'
    text=path.read_text(encoding='utf-8-sig')
    if 'SimplyLoveStreamReceptorFeedback' in text:return
    variants=['''        -- SimplyLoveStreamLowerHUD: same +180 shift as the trial/BPM block.
        judgmentY = _screen.cy + 100
        comboY = _screen.cy + 140''','''        judgmentY = _screen.cy - 80
        comboY = _screen.cy - 40''']
    old=next((v for v in variants if v in text),None)
    if old is None:raise RuntimeError('Unexpected stream judgment layout')
    text=text.replace(old,'''        -- SimplyLoveStreamReceptorFeedback: judgment / receptors / combo.
        judgmentY = _screen.cy - 180
        comboY = _screen.cy - 76''',1)
    text=text.replace('SimplyLoveStreamCompactJudgment: keep feedback just below receptors.',
                      'SimplyLoveStreamCompactJudgment: streaming feedback around receptors.')
    path.write_text(text,encoding='utf-8')


if __name__=='__main__':
    import sys
    install(sys.argv[1])
