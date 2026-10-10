"""Keep Simply Love background music confined to gameplay while streaming."""
from pathlib import Path
import argparse
import re


def install(root):
    theme = root / 'Themes/Simply Love'
    path = theme / 'metrics.ini'
    text = path.read_text(encoding='utf-8-sig')
    if '# SimplyLoveStreamQuietMenus' not in text:
        text = text.replace('[ScreenWithMenuElements]', '''[ScreenWithMenuElements]
# SimplyLoveStreamQuietMenus
PlayMusic=not PREFSMAN:GetPreference("StreamerMode")''', 1)
        text = re.sub(r'(\[ScreenGameOver\][\s\S]*?\n)PlayMusic=true',
                      r'\1PlayMusic=not PREFSMAN:GetPreference("StreamerMode")', text, count=1)
        text = text.replace('[ScreenSelectMusic]', '''[ScreenSelectMusic]
# The engine checks this delay even for forced previews. Infinite delay
# disables previews without muting the independent gameplay sound.
SampleMusicDelayInit=PREFSMAN:GetPreference("StreamerMode") and math.huge or 0''', 1)
        text += '''
[ScreenHowToPlay]
PlayMusic=not PREFSMAN:GetPreference("StreamerMode")
'''
        path.write_text(text, encoding='utf-8')
    path = theme / 'Scripts/SL-SelectMusicHelpers.lua'
    text = path.read_text(encoding='utf-8-sig')
    if '-- SimplyLoveStreamQuietPreview' not in text:
        text = text.replace('play_sample_music = function()', '''play_sample_music = function()
    if PREFSMAN:GetPreference("StreamerMode") then -- SimplyLoveStreamQuietPreview
        SOUND:StopMusic()
        return
    end''', 1)
        path.write_text(text, encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent.parent)
    install(parser.parse_args().root)
