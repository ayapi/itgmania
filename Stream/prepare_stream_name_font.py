"""Build a cached Noto Sans JP Bold bitmap font for native stream names.

Requires Pillow. Generated assets and downloaded font data stay in the runtime.
"""
from pathlib import Path
from urllib.request import urlretrieve
import argparse,math,unicodedata
from PIL import Image,ImageDraw,ImageFont


def characters():
    values=set(range(0x20,0x100))|set(range(0x3000,0x3100))|set(range(0xff01,0xffa0))
    for lead in list(range(0x81,0xa0))+list(range(0xe0,0xfd)):
        for trail in range(0x40,0xfd):
            try:
                text=bytes([lead,trail]).decode('cp932')
            except UnicodeDecodeError:
                continue
            if len(text)==1 and unicodedata.category(text)!='Co':
                values.add(ord(text))
    return sorted(values)


def install(root,font_path=None):
    root=Path(root)
    cache=root/'Save/GiftAPI/font-cache';cache.mkdir(parents=True,exist_ok=True)
    if font_path is None:
        font_path=cache/'NotoSansJP.ttf'
        if not font_path.exists():
            urlretrieve('https://raw.githubusercontent.com/google/fonts/main/ofl/notosansjp/NotoSansJP%5Bwght%5D.ttf',font_path)
    license_path=cache/'NotoSansJP-OFL.txt'
    if not license_path.exists():
        urlretrieve('https://raw.githubusercontent.com/google/fonts/main/ofl/notosansjp/OFL.txt',license_path)
    font=ImageFont.truetype(str(font_path),32)
    font.set_variation_by_axes([700])
    directory=root/'Themes/Simply Love/Fonts';directory.mkdir(parents=True,exist_ok=True)
    prefix='Stream Noto Sans JP'
    chars=characters();columns=25;rows=23;capacity=columns*rows
    settings=['[common]','DefaultWidth=16','LineSpacing=18','Top=2','Baseline=18',
              'DrawExtraPixelsLeft=1','DrawExtraPixelsRight=1','AdvanceExtraPixels=0']
    for page,start in enumerate(range(0,len(chars),capacity)):
        subset=chars[start:start+capacity];actual_rows=math.ceil(len(subset)/columns)
        atlas=Image.new('RGBA',(columns*40,actual_rows*44));draw=ImageDraw.Draw(atlas)
        settings.extend(['',f'[page{page:02}]'])
        for index,codepoint in enumerate(subset):
            char=chr(codepoint);advance=font.getlength(char)
            x=index%columns*40+(40-advance)/2;y=index//columns*44+36
            draw.text((x,y),char,font=font,fill='white',anchor='ls')
            settings.extend([f'map U+{codepoint:04X}={index}',f'{index}={max(1,round(advance/2))}'])
            if char=='?':settings.append(f'map U+F8FF={index}')
        atlas.save(directory/f'{prefix} [page{page:02}] {columns}x{actual_rows} (doubleres).png')
    (directory/(prefix+'.ini')).write_text('\n'.join(settings)+'\n',encoding='utf-8')
    # Font loading glob-matches this prefix without checking extensions.
    # Keep the license beside the downloaded TTF, outside the font directory.
    print(f'Noto Sans JP Bold: {len(chars)} characters, {math.ceil(len(chars)/capacity)} cached pages',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);parser.add_argument('--font',type=Path)
    args=parser.parse_args();install(args.root,args.font)
