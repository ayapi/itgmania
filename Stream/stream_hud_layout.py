"""Place combo and judgment above receptors, with BPM/trials below."""
from pathlib import Path


def install(root):
    path=Path(root)/'Themes/Simply Love/Scripts/SL-Layout.lua'
    text=path.read_text(encoding='utf-8-sig')
    if 'SimplyLoveStreamTopComboFeedback' in text:return
    variants=['''        -- SimplyLoveStreamReceptorFeedback: judgment / receptors / combo.
        judgmentY = _screen.cy - 180
        comboY = _screen.cy - 76''','''        -- SimplyLoveStreamLowerHUD: same +180 shift as the trial/BPM block.
        judgmentY = _screen.cy + 100
        comboY = _screen.cy + 140''','''        judgmentY = _screen.cy - 80
        comboY = _screen.cy - 40''']
    old=next((v for v in variants if v in text),None)
    if old is None:raise RuntimeError('Unexpected stream judgment layout')
    text=text.replace(old,'''        -- SimplyLoveStreamTopComboFeedback: combo / judgment / receptors.
        judgmentY = _screen.cy - 172
        comboY = _screen.cy - 204''',1)
    # The original theme pushes combo below judgment at the end of layout.
    # Keep surrounding optional UI, then restore this intentional top position.
    anchor='    return layout\nend'
    if anchor not in text:raise RuntimeError('Unknown gameplay layout return')
    text=text.replace(anchor,'''    if PREFSMAN:GetPreference("StreamerMode") and not reverse then
        layout.Combo.y = comboY
    end
    return layout
end''',1)
    text=text.replace('SimplyLoveStreamCompactJudgment: keep feedback just below receptors.',
                      'SimplyLoveStreamCompactJudgment: streaming feedback around receptors.')
    path.write_text(text,encoding='utf-8')


if __name__=='__main__':
    import sys
    install(sys.argv[1])
