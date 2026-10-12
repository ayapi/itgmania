"""Enable native ITG life changes in Simply Love's streaming Casual mode."""
from pathlib import Path
import argparse,re,shutil


def fix_fail_tracking(root):
    path=Path(root)/'Themes/Simply Love/BGAnimations/ScreenGameplay overlay/TrackFailTime.lua'
    text=path.read_text(encoding='utf-8-sig')
    marker='-- SimplyLoveStreamLifeSafeFailTracking'
    if marker in text:
        return
    anchor='if streams.NotesPerMeasure[currentMeasure+1] >= 16 then'
    if text.count(anchor)!=1:
        raise ValueError('Unexpected Simply Love fail-time tracking')
    backup=path.with_name('TrackFailTime.lua.before-stream-life')
    if not backup.exists():
        shutil.copy2(path,backup)
    text=text.replace(anchor,marker+'\n\t\t\tif streams and streams.NotesPerMeasure and streams.Measures and (streams.NotesPerMeasure[currentMeasure+1] or 0) >= 16 then')
    path.write_text(text,encoding='utf-8')


def install(root):
    fix_fail_tracking(root)
    path=Path(root)/'Themes/Simply Love/metrics.ini'
    text=path.read_text(encoding='utf-8-sig')
    marker='# SimplyLoveStreamCasualLife: use native ITG life without changing Casual timing.'
    if marker in text:
        return
    start=text.index('[LifeMeterBar]')
    end=text.index('\n[',start+1)
    section=text[start:end]
    pattern=r'(?m)^(LifePercentChange\w+)=SL\.Metrics\[SL\.Global\.GameMode\]\["\1"\]$'
    section,count=re.subn(pattern,lambda match:
        match[1]+'=SL.Metrics[(PREFSMAN:GetPreference("StreamerMode") and SL.Global.GameMode=="Casual") and "ITG" or SL.Global.GameMode]["'+match[1]+'"]',section)
    if count!=9:
        raise ValueError('Unexpected Simply Love native life metrics')
    backup=path.with_name('metrics.ini.before-stream-life')
    if not backup.exists():
        shutil.copy2(path,backup)
    text=text[:start]+marker+'\n'+section+text[end:]
    path.write_text(text,encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True)
    install(parser.parse_args().root)
