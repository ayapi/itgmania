"""Import the supplied PNG design and bake its OFL fonts for the native HUD."""
from pathlib import Path
import argparse
import json
import shutil

SOURCE = Path(__file__).resolve().parent


def install(root):
    theme = Path(root)/'Themes/Simply Love'
    shutil.copytree(SOURCE/'ChallengeAssets', theme/'BGAnimations/ScreenGameplay overlay/ChallengeAssets', dirs_exist_ok=True)
    for path in (SOURCE/'ChallengeFonts').iterdir():
        shutil.copy2(path, theme/'Fonts'/path.name)
    for name in ('ChallengePresentation.lua', 'ChallengeDesign.lua'):
        shutil.copy2(SOURCE/name, theme/'BGAnimations/ScreenGameplay overlay'/name)


def bake_font(path, output, family):
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    font = ImageFont.truetype(str(path), 64)
    if 'Variable' in path.name:
        font.set_variation_by_axes([700])
    chars = ''.join(chr(c) for c in range(32, 127))
    atlas = Image.new('RGBA', (16*80, 6*96))
    draw = ImageDraw.Draw(atlas)
    settings = ['[common]', 'DefaultWidth=24', 'LineSpacing=40', 'Top=0', 'Baseline=36', '', '[main]']
    for i, char in enumerate(chars):
        advance = font.getlength(char)
        draw.text((i%16*80+(80-advance)/2, i//16*96+72), char, font=font, fill='white', anchor='ls')
        settings.extend([f'range Unicode #{ord(char):04X}-{ord(char):04X}={i}', f'{i}={max(1,round(advance/2))}'])
        if char == '?': settings.append(f'map default={i}')
    atlas.save(output/f'{family} [main] 16x6 (doubleres).png')
    if family == 'Stream Challenge Delta':
        glow = Image.new('RGBA', atlas.size, 'white')
        glow.putalpha(atlas.getchannel('A').filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(4)))
        glow.save(output/f'{family} [main-stroke] 16x6 (doubleres).png')
    (output/f'{family}.ini').write_text('\n'.join(settings)+'\n', encoding='utf-8')


def import_parts(parts):
    parts = Path(parts)
    assets = SOURCE/'ChallengeAssets'
    assets.mkdir(exist_ok=True)
    countdown = json.loads((parts/'countdown-layout/layout.json').read_text(encoding='utf-8-sig'))
    rects = []
    for key, data in countdown['assets'].items():
        file = f'countdown/{key}.png'
        dest = assets/file
        dest.parent.mkdir(exist_ok=True)
        shutil.copy2(parts/'countdown-layout'/data['file'], dest)
        x,y = data['render_top_left']; w,h = data['render_size']
        rects.append(f' ["{key}"]={{file="{file}",x={x-550:.6f},y={y-1065:.6f},w={w},h={h}}},')
    meter = parts/'challenge-meter'
    for folder in ('attack', 'cleared', 'shared', 'titles'):
        shutil.copytree(meter/folder, assets/folder, dirs_exist_ok=True)
    shutil.copy2(parts/'countdown-layout/layout.json', assets/'countdown-layout.json')
    shutil.copy2(meter/'layout.json', assets/'meter-layout.json')
    licenses = assets/'licenses'; licenses.mkdir(exist_ok=True)
    fonts = SOURCE/'ChallengeFonts'; fonts.mkdir(exist_ok=True)
    for ttf, license_name, family in (
        ('Rajdhani-Bold.ttf', 'OFL.txt', 'Stream Challenge Counter'),
        ('Oxanium-Variable.ttf', 'Oxanium-Variable-OFL.txt', 'Stream Challenge Delta'),
    ):
        shutil.copy2(meter/'fonts'/license_name, licenses/f'{family}.txt')
        shutil.copy2(meter/'fonts'/ttf, licenses/ttf)
        bake_font(meter/'fonts'/ttf, fonts, family)
    (SOURCE/'ChallengeDesign.lua').write_text(
        '-- Imported from the supplied portrait layout. Scale uniformly relative to native BPM.\n'
        'return {scale=0.32,anchor_y=208.8,countdown={\n'+'\n'.join(rects)+'\n}}\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--parts', type=Path)
    parser.add_argument('--root', type=Path)
    args = parser.parse_args()
    if args.parts: import_parts(args.parts)
    if args.root: install(args.root)
