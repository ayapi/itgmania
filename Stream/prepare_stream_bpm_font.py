"""Build the local Beast Machines BPM fonts; no font assets go in Git."""
from pathlib import Path
from zipfile import ZipFile
from PIL import Image
from import_beast_font import label
import argparse


def install(root, archive):
    with ZipFile(archive) as z:
        data = z.read('Beast Machines.TTF')
    directory = root / 'Themes/Simply Love/Fonts'
    directory.mkdir(parents=True, exist_ok=True)
    characters = 'BPM0123456789.'
    for name, color in [('Base', '#48d9ff'), ('Up', '#ff4040'), ('Down', '#39d638')]:
        atlas = Image.new('RGBA', (96*len(characters), 64))
        widths = []
        for index, char in enumerate(characters):
            glyph = label(data, char, color, size=34)
            assert glyph.width <= 96 and glyph.height <= 64
            atlas.alpha_composite(glyph, (index*96+(96-glyph.width)//2, (64-glyph.height)//2))
            widths.append(f'{index}={(glyph.width+1)//2+3}')
        prefix = 'Stream BPM '+name
        atlas.save(directory / f'{prefix} {len(characters)}x1 (doubleres).png')
        (directory / (prefix+'.ini')).write_text(
            '[Char Widths]\nline 0='+characters+'\nDefaultWidth=30\nAdvanceExtraPixels=-3\n'+
            '\n'.join(widths)+'\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--archive', required=True, type=Path)
    args = parser.parse_args()
    install(args.root, args.archive)
