"""Build local bitmap assets from the user's Beast Machines font archive."""
from pathlib import Path
from zipfile import ZipFile
from io import BytesIO
import argparse
from PIL import Image, ImageDraw, ImageFont, ImageFilter


def label(font_data, text, color, size=74):
    font = ImageFont.truetype(BytesIO(font_data), size)
    bounds = font.getbbox(text, stroke_width=2)
    canvas = Image.new('RGBA', (bounds[2]-bounds[0]+8, bounds[3]-bounds[1]+8))
    ImageDraw.Draw(canvas).text((4-bounds[0], 4-bounds[1]), text, font=font,
                               fill='white', stroke_width=2, stroke_fill=color)
    return canvas


def install(root, archive):
    with ZipFile(archive) as zip_file:
        data = zip_file.read('Beast Machines.TTF')
    theme = root / 'Themes/Simply Love'
    width, height = 440, 148
    atlas = Image.new('RGBA', (width*2, height*7))
    names = ['FANTASTIC', 'FANTASTIC', 'EXCELLENT', 'GREAT', 'DECENT', 'WAY OFF', 'MISS']
    colors = ['#48d9ff', '#b6b6b6', '#ffdc00', '#39d638', '#b24fff', '#ff9000', '#ff4040']
    for row, (text, color) in enumerate(zip(names, colors)):
        for col in range(2):
            word = text if row in (0, 6) else ('-' + text if col == 0 else text + '-')
            glyph = label(data, word, color)
            scale = min(1, 400/glyph.width, 82/glyph.height)
            glyph = glyph.resize((round(glyph.width*scale), round(glyph.height*scale)), Image.Resampling.LANCZOS)
            x, y = col*width+(width-glyph.width)//2, row*height+(height-glyph.height)//2
            glow = Image.new('RGBA', glyph.size, color)
            glow.putalpha(glyph.getchannel('A').filter(ImageFilter.GaussianBlur(5)).point(lambda a: a//2))
            atlas.alpha_composite(glow, (x, y))
            atlas.alpha_composite(glyph, (x, y))
    filename = 'Beast Machines 2x7 (doubleres).png'
    atlas.save(theme/'Graphics/_judgments'/filename)
    directory = theme/'Fonts/_Combo Fonts/Beast Machines'
    directory.mkdir(parents=True, exist_ok=True)
    digits = Image.new('RGBA', (1240, 200))
    for index, character in enumerate('1234567890'):
        glyph = label(data, character, '#ffffff', 74)
        scale = min(1, 100/glyph.width, 78/glyph.height)
        glyph = glyph.resize((round(glyph.width*scale), round(glyph.height*scale)), Image.Resampling.LANCZOS)
        digits.alpha_composite(glyph, (index*124+(124-glyph.width)//2, (200-glyph.height)//2))
    digits.save(directory/'Beast Machines 10x1 (doubleres).png')
    (directory/'Beast Machines.ini').write_text(
        '[Char Widths]\nline 0=1234567890\nDefaultWidth=52\nAddToAllWidths=0\n', encoding='utf-8')
    for name, anchor, replacement in [
        ('Player judgment.lua', 'if file_to_load == "None" then',
         'if PREFSMAN:GetPreference("StreamerMode") then file_to_load="'+filename+'" end\n\nif file_to_load == "None" then'),
        ('Player combo.lua', 'if mods.HideCombo or combo_font == nil then',
         'if PREFSMAN:GetPreference("StreamerMode") then combo_font="Beast Machines" end\n\nif mods.HideCombo or combo_font == nil then')]:
        path = theme/'Graphics'/name
        text = path.read_text(encoding='utf-8-sig')
        if '-- SimplyLoveBeastMachines' not in text:
            if anchor not in text:raise ValueError('Unexpected player graphic: '+name)
            text = text.replace(anchor, '-- SimplyLoveBeastMachines\n'+replacement, 1)
            path.write_text(text, encoding='utf-8')
    preview = Image.new('RGBA', (440, 7*148+140))
    for row in range(7):preview.alpha_composite(atlas.crop((0,row*148,440,(row+1)*148)), (0,row*148))
    number = label(data, '123456', '#ffffff', 74)
    number.thumbnail((400,100), Image.Resampling.LANCZOS)
    preview.alpha_composite(number, ((440-number.width)//2,7*148+20))
    preview.save(root/'Stream/beast-font-preview.png')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--archive', type=Path, required=True)
    args = parser.parse_args()
    install(args.root, args.archive)
