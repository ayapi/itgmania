"""Shorten judgment entrance and exit only in the streaming setup."""
from pathlib import Path
import argparse

def install(root):
    path=Path(root)/'Themes/Simply Love/Graphics/Player judgment.lua'
    text=path.read_text(encoding='utf-8-sig')
    if '-- SimplyLoveStreamFastJudgment' in text:return
    before='sprite:zoom(0.8):decelerate(0.1):zoom(0.75):sleep(0.6):accelerate(0.2):zoom(0)'
    if text.count(before)!=2:raise ValueError('Unexpected Simply Love judgment animation')
    helper='''-- SimplyLoveStreamFastJudgment: crisp movement, retain the readable hold.
local function animateJudgment(sprite)
 local stream=PREFSMAN:GetPreference("StreamerMode")
 sprite:zoom(0.8):decelerate(stream and 0.03 or 0.1):zoom(0.75)
  :sleep(0.6):accelerate(stream and 0.07 or 0.2):zoom(0)
end

'''
    path.write_text(helper+text.replace(before,'animateJudgment(sprite)'),encoding='utf-8')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True)
    install(parser.parse_args().root)
