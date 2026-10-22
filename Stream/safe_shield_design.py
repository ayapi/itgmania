"""Import/deploy the user's SAFE SHIELD PNG layout without changing settings."""
from pathlib import Path
import argparse,json,shutil

SOURCE=Path(__file__).resolve().parent


def install(root):
    overlay=Path(root)/'Themes/Simply Love/BGAnimations/ScreenGameplay overlay'
    shutil.copytree(SOURCE/'SafeShieldAssets',overlay/'SafeShieldAssets',dirs_exist_ok=True)
    for name in ('SafeShield.lua','SafeShieldDesign.lua','SafeShieldPresentation.lua'):
        shutil.copy2(SOURCE/name,overlay/name)


def import_layout(folder):
    folder=Path(folder);layout=json.loads((folder/'layout.json').read_text(encoding='utf-8-sig'))
    target=SOURCE/'SafeShieldAssets';target.mkdir(exist_ok=True)
    shutil.copy2(folder/'layout.json',target/'layout.json')
    rects=[]
    for key,a in layout['assets'].items():
        filename=Path(a['file']).name
        shutil.copy2(folder/a['file'],target/filename)
        x,y=a['render_top_left'];w,h=a['render_size']
        rects.append(f' {key}={{file="{filename}",x={x-550:.6f},y={y-1065:.6f},w={w},h={h}}},')
    (SOURCE/'SafeShieldDesign.lua').write_text(
        '-- Uniform portrait-to-native conversion shared with the challenge design.\n'
        'return {scale=0.32,anchor_y=208.8,assets={\n'+'\n'.join(rects)+'\n}}\n',encoding='utf-8')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--layout',type=Path);p.add_argument('--root',type=Path)
    args=p.parse_args()
    if args.layout:import_layout(args.layout)
    if args.root:install(args.root)
