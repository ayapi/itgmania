"""Install V5 presentation without replacing user settings or theme layouts."""
from pathlib import Path
import shutil

def install(root):
 root=Path(root);theme=root/'Themes/Simply Love';source=Path(__file__).parent
 underlay=theme/'BGAnimations/ScreenGameplay underlay'
 shutil.copy2(source/'TrialGlow.lua',underlay/'TrialGlow.lua')
 p=underlay/'default.lua';text=p.read_text(encoding='utf-8-sig');hook='if PREFSMAN:GetPreference("StreamerMode") then t[#t+1]=LoadActor("./TrialGlow.lua") end -- StreamV5Glow'
 if hook not in text:text=text.replace('return t',hook+'\nreturn t');p.write_text(text,encoding='utf-8')
 paths=['BGAnimations/ScreenGameplay overlay/TrackFailTime.lua','BGAnimations/ScreenEvaluation common/PerPlayer/Upper/LetterGrade.lua','BGAnimations/ScreenEvaluationSummary overlay/LetterGrades.lua']
 guard='if PREFSMAN:GetPreference("StreamerMode") then return Def.ActorFrame{} end -- StreamV5NoLifeGrade\n'
 for relative in paths:
  p=theme/relative
  if p.exists():
   text=p.read_text(encoding='utf-8-sig')
   if 'StreamV5NoLifeGrade' not in text:shutil.copy2(p,p.with_name(p.name+'.before-v5'));p.write_text(guard+text,encoding='utf-8')
