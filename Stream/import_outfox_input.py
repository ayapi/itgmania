"""Convert OutFox joystick button names to ITGmania's Keymaps format."""
from pathlib import Path
from datetime import datetime
import argparse
import re
import shutil


def install(root, outfox):
    source = outfox / 'Save/Keymaps.ini'
    target = root / 'Save/Keymaps.ini'
    text = source.read_text(encoding='utf-8-sig')
    text = re.sub(r'(Joy\d+_)Button (\d+)', r'\1B\2', text)
    text = re.sub(r'(?m)^([12])_=.*\n?', '', text)
    if target.exists():
        backup = target.with_name('Keymaps.ini.before-input-import-' +
                                  datetime.now().strftime('%Y%m%d-%H%M%S'))
        shutil.copy2(target, backup)
    target.write_text(text, encoding='utf-8')
    print('Converted OutFox pad bindings into ' + str(target))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--outfox', type=Path, default=Path('C:/Games/OutFox 0.5.0 Alpha Win64'))
    args = parser.parse_args()
    install(args.root, args.outfox)
