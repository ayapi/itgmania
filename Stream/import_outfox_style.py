"""Import the user's installed skin and beat bars locally, without bundling assets."""
from pathlib import Path
import argparse,configparser,re,shutil

def install(root, outfox):
    source=outfox/'Appearance/NoteSkins/dance/SCH-CLASSIC-SMNOTE'
    if not source.is_dir():raise SystemExit('SCH-CLASSIC-SMNOTE not found: '+str(source))
    skin=root/'NoteSkins/dance/SCH-CLASSIC-SMNOTE'
    shutil.copytree(source,skin,dirs_exist_ok=True,ignore=shutil.ignore_patterns('*.before-*'))
    path=skin/'NoteSkin.lua'
    text=path.read_text(encoding='utf-8-sig')
    # ITGmania's NoteDisplay already fades alpha; no OutFox draw wrapper needed.
    text=re.sub(r'(?m)^.*-- SimplyLoveStreamNoteAlpha\s*$', '',text)
    path.write_text(text,encoding='utf-8')
    # Transparent output cannot use an opaque black flash as its "off" state.
    path=skin/'Fallback Explosion.lua'
    text=path.read_text(encoding='utf-8-sig').replace('diffuse(0,0,0,1)', 'diffusealpha(0)')
    path.write_text(text,encoding='utf-8')
    theme=root/'Themes/Simply Love'
    path=theme/'metrics.ini';text=path.read_text(encoding='utf-8-sig')
    text=re.sub(r'(?m)^DefaultNoteSkinName=.*$', 'DefaultNoteSkinName="sch-classic-smnote"',text)
    section='\n[NoteField]\nShowBeatBars=true\nBarMeasureAlpha=1\nBar4thAlpha=0.5\nBar8thAlpha=0\nBar16thAlpha=0\n'
    if '[NoteField]' in text:text=re.sub(r'(?ms)^\[NoteField\]\n.*?(?=^\[|\Z)',section.lstrip(),text)
    else:text+=section
    path.write_text(text,encoding='utf-8')
    bar=outfox/'Appearance/Themes/_fallback/Graphics/NoteField bars 1x4.png'
    (theme/'Graphics').mkdir(exist_ok=True)
    shutil.copy2(bar,theme/'Graphics'/bar.name)
    # This Simply Love version overrides the NoteField metrics at runtime.
    # Match the source's measure/quarter bars while streaming.
    path=theme/'BGAnimations/ScreenGameplay underlay/PerPlayer/NoteField/default.lua'
    text=path.read_text(encoding='utf-8-sig')
    tag='-- ImportedOutFoxBeatBars'
    if tag not in text:
        anchor='if mods.MeasureLines == "Off" then'
        if anchor not in text:raise SystemExit('Unexpected Simply Love beat bar controller')
        text=text.replace(anchor,'''if PREFSMAN:GetPreference("StreamerMode") then -- ImportedOutFoxBeatBars
      notefield:SetBeatBars(true)
      notefield:SetBeatBarsAlpha(1, 0.5, 0, 0)
    elseif mods.MeasureLines == "Off" then''',1)
        path.write_text(text,encoding='utf-8')
    path=root/'Save/Preferences.ini'
    cfg=configparser.ConfigParser(interpolation=None);cfg.optionxform=str;cfg.read(path,encoding='utf-8-sig')
    cfg['Options']['RateModPreservesPitch']='0'
    # Casual mode hides songs beyond the single-stage length cutoff.
    # Preserve the source installation's cutoffs along with its visual settings.
    previous=configparser.ConfigParser(interpolation=None);previous.optionxform=str
    previous.read(outfox/'Save/Preferences.ini',encoding='utf-8-sig')
    for key in ('LongVerSongSeconds','MarathonVerSongSeconds'):
        if previous.has_option('Options',key):
            cfg['Options'][key]=previous['Options'][key]
    for section in ['Options','Game-dance']:
        if not cfg.has_section(section):cfg.add_section(section)
        mods=[v.strip() for v in cfg[section].get('DefaultModifiers','').split(',') if v.strip()]
        names={p.name.casefold() for p in (root/'NoteSkins/dance').iterdir() if p.is_dir()}
        mods=[v for v in mods if v.casefold() not in names]
        mods.append('Sch-classic-smnote')
        cfg[section]['DefaultModifiers']=', '.join(mods)
    with path.open('w',encoding='utf-8') as handle:cfg.write(handle,space_around_delimiters=False)
    print('Imported SCH-CLASSIC-SMNOTE and beat bars; enabled speed-dependent pitch')

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--outfox',type=Path,default=Path('C:/Games/OutFox 0.5.0 Alpha Win64'))
    args=parser.parse_args();install(args.root,args.outfox)
