"""Embed the user's local font into the OBS page without publishing the font."""
from pathlib import Path
from zipfile import ZipFile
import argparse,base64,re

def install(root, archive):
    with ZipFile(archive) as source:
        data=source.read('Beast Machines.TTF')
    path=Path(root)/'Stream/overlay.html'
    css='@font-face{font-family:"Beast Machines";src:url("data:font/ttf;base64,'+base64.b64encode(data).decode('ascii')+'");font-display:block}'
    text=path.read_text(encoding='utf-8-sig')
    text,count=re.subn(r'/\* BEGIN LOCAL BEAST FONT \*/.*?/\* END LOCAL BEAST FONT \*/',
        '/* BEGIN LOCAL BEAST FONT */\n'+css+'\n/* END LOCAL BEAST FONT */',text,flags=re.S)
    if count!=1:raise ValueError('Missing local font placeholder')
    path.write_text(text,encoding='utf-8')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);parser.add_argument('--archive',type=Path,required=True)
    args=parser.parse_args();install(args.root,args.archive)
