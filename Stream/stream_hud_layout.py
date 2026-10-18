"""Move streaming judgments/combo down with the trial/BPM block."""
from pathlib import Path


def install(root):
    path=Path(root)/'Themes/Simply Love/Scripts/SL-Layout.lua'
    text=path.read_text(encoding='utf-8-sig')
    if 'SimplyLoveStreamLowerHUD' in text:return
    old='''        judgmentY = _screen.cy - 80
        comboY = _screen.cy - 40'''
    if old not in text:raise RuntimeError('Unexpected stream judgment layout')
    text=text.replace(old,'''        -- SimplyLoveStreamLowerHUD: same +180 shift as the trial/BPM block.
        judgmentY = _screen.cy + 100
        comboY = _screen.cy + 140''',1)
    path.write_text(text,encoding='utf-8')


if __name__=='__main__':
    import sys
    install(sys.argv[1])
