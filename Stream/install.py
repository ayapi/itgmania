"""Install the stream/gift theme addon into this fork's portable runtime."""
from pathlib import Path
import argparse, configparser, json, re, shutil
from quiet_menus import install as quiet_menus

def install(root):
    root = root.resolve()
    source = Path(__file__).resolve().parent
    theme = root/'Themes/Simply Love'
    overlay = theme/'BGAnimations/ScreenGameplay overlay'
    if not (overlay/'default.lua').is_file():
        raise SystemExit('Simply Love is missing from '+str(root))
    for name in ('GiftAPI.lua', 'GiftAPI.Json.lua', 'StreamArrowFade.lua', 'StreamEdgeFade.lua'):
        shutil.copy2(source/name, overlay/name)
    path = overlay/'default.lua'
    text = path.read_text(encoding='utf-8-sig')
    hook = 'af[#af+1] = LoadActor("./GiftAPI.lua") -- SimplyLoveGiftAPI'
    if hook not in text:
        shutil.copy2(path, path.with_name(path.name+'.before-giftapi'))
        text = text.replace('return af', hook+'\nreturn af')
        path.write_text(text, encoding='utf-8')
    text = path.read_text(encoding='utf-8-sig')
    edge_hook = 'af[#af+1] = LoadActor("./StreamEdgeFade.lua") -- SimplyLoveStreamEdgeFade'
    if edge_hook not in text:
        text = text.replace('return af', edge_hook+'\nreturn af')
        path.write_text(text, encoding='utf-8')
    path = theme/'BGAnimations/ScreenGameplay underlay/default.lua'
    text = path.read_text(encoding='utf-8-sig')
    if '-- SimplyLoveStreamRGBA' not in text:
        shutil.copy2(path, path.with_name(path.name+'.before-stream'))
        # Copy opaque black first; the second quad clears alpha. Actors with
        # diffusealpha(0) can be culled before drawing, so do not use that.
        clear = '''
if PREFSMAN:GetPreference("StreamerMode") then
 t[#t+1] = Def.ActorFrame{ -- SimplyLoveStreamRGBA
  Def.Quad{InitCommand=function(self)
   self:xy(_screen.cx,_screen.cy):zoomto(_screen.w,_screen.h):blend("BlendMode_CopySrc"):diffuse(0,0,0,1)
  end},
  Def.Quad{InitCommand=function(self)
   self:xy(_screen.cx,_screen.cy):zoomto(_screen.w,_screen.h):blend("BlendMode_AlphaKnockOut"):diffuse(1,1,1,1)
  end},
 }
end
'''
        anchor = 'for player in ivalues(Players) do'
        if anchor not in text:
            raise SystemExit('Unexpected Simply Love gameplay underlay')
        text = text.replace(anchor, clear+'\n'+anchor, 1)
        hide = r'(?m)^(\s*)(t\[#t\+1\] = LoadActor\("(?:\./Shared/(?:Header|SongInfoBar|BPMDisplay|VersusStepStatistics)\.lua|\./PerPlayer/(?:Danger|BackgroundFilter|UpperNPSGraph|Score|DifficultyMeter)\.lua|\./PerPlayer/(?:LifeMeter|TargetScore|StepStatistics)/default\.lua)"(?:, player)?\))([^\r\n]*)$'
        text = re.sub(hide, r'\1if not PREFSMAN:GetPreference("StreamerMode") then \2 end -- SimplyLoveStreamHideUI\3', text)
        path.write_text(text, encoding='utf-8')
    path = theme/'Scripts/SL-Layout.lua'
    text = path.read_text(encoding='utf-8-sig')
    if '-- SimplyLoveStreamCompactJudgment' not in text:
        anchor = '    local judgmentHeight = 40'
        if anchor not in text:raise SystemExit('Unexpected Simply Love feedback layout')
        text = text.replace(anchor, '''    -- SimplyLoveStreamCompactJudgment: keep feedback just below receptors.
    if PREFSMAN:GetPreference("StreamerMode") and not reverse then
        judgmentY = _screen.cy - 80
        comboY = _screen.cy - 40
    end
    local judgmentHeight = 40''', 1)
        text = text.replace('        Combo = { y = comboY },',
                            '        Combo = { y = comboY },\n        Judgment = { y = judgmentY },', 1)
        text += '''
-- Share the same anchor with surrounding feedback and combo layout.
function JudgmentTransformCommand(self, params)
    local layout = GetGameplayLayout(params.Player, params.bReverse)
    self:xy(0, layout.Judgment.y - _screen.cy)
end
'''
        path.write_text(text, encoding='utf-8')
    # Native ITGmania tap fading already changes alpha rather than dimming RGB.
    save = root/'Save';(save/'GiftAPI').mkdir(parents=True,exist_ok=True)
    if not (save/'GiftAPI/config.json').exists():
        shutil.copy2(source/'config.json',save/'GiftAPI/config.json')
    path = save/'Preferences.ini'
    cfg = configparser.ConfigParser(interpolation=None);cfg.optionxform=str
    if path.exists():cfg.read(path,encoding='utf-8-sig')
    if not cfg.has_section('Options'):cfg.add_section('Options')
    # Leave existing choices intact; match the source setup's 50% volume
    # when creating a new portable installation.
    cfg['Options'].setdefault('SoundVolume', '0.500000')
    cfg['Options'].setdefault('RateModPreservesPitch', '0')
    for key,value in dict(Theme='Simply Love',StreamerMode='1',Windowed='1',DisplayColorDepth='32',VideoRenderers='opengl',AllowMultipleInstances='1').items():cfg['Options'][key]=value
    with path.open('w',encoding='utf-8') as handle:cfg.write(handle,space_around_delimiters=False)
    (root/'Portable.ini').touch(exist_ok=True)
    quiet_menus(root)
    (root/'start-game.cmd').write_bytes(
        b'@echo off\r\ncd /d "%~dp0"\r\n'
        b'python Stream\\start_obs_background.py\r\n'
        b'python Stream\\start_game_background.py\r\n')
    print('Installed streaming/gifts into '+str(root))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parent.parent)
    install(parser.parse_args().root)
