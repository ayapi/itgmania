"""Install the compact evaluation screen only for StreamerMode."""
from pathlib import Path
import shutil


def install(root):
    theme=Path(root)/'Themes/Simply Love'
    common=theme/'BGAnimations/ScreenEvaluation common'
    shutil.copy2(Path(__file__).with_name('StreamEvaluation.lua'),common/'StreamEvaluation.lua')
    path=common/'default.lua'
    text=path.read_text(encoding='utf-8-sig')
    marker='-- StreamCompactEvaluation'
    if marker not in text:
        anchor='local t = Def.ActorFrame{Name="ScreenEval Common"}'
        if anchor not in text:
            raise RuntimeError('Unknown Simply Love evaluation layout; no hook applied')
        shutil.copy2(path,path.with_name(path.name+'.before-stream-results'))
        text=text.replace(anchor,anchor+'\nif PREFSMAN:GetPreference("StreamerMode") then local result=LoadActor("./StreamEvaluation.lua"); return result end '+marker)
        path.write_text(text,encoding='utf-8')
    elif 'then return LoadActor("./StreamEvaluation.lua") end' in text:
        path.write_text(text.replace('then return LoadActor("./StreamEvaluation.lua") end',
            'then local result=LoadActor("./StreamEvaluation.lua"); return result end'),encoding='utf-8')
    for relative in ['ScreenEvaluationStage background.lua','ScreenEvaluationStage in/default.lua']:
        path=theme/'BGAnimations'/relative
        text=path.read_text(encoding='utf-8-sig')
        if marker not in text:
            shutil.copy2(path,path.with_name(path.name+'.before-stream-results'))
            path.write_text('if PREFSMAN:GetPreference("StreamerMode") then return Def.ActorFrame{} end '+marker+'\n'+text,encoding='utf-8')


if __name__=='__main__':
    import sys
    install(Path(sys.argv[1]))
