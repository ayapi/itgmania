"""Emit the two complete HTML documents for the LAN display server."""
from pathlib import Path


def build(directory=None):
    directory=Path(directory) if directory else Path(__file__).resolve().parent
    html=(directory/'overlay.html').read_text(encoding='utf-8-sig')
    for platform in ('tiktok','youtube'):
        title='TikTok' if platform=='tiktok' else 'YouTube'
        document=html.replace('<title>ITGmania 配信情報</title>',f'<title>ITGmania {title} 配信情報</title>\n<meta name="stream-platform" content="{platform}">')
        (directory/f'overlay-{platform}.html').write_text(document,encoding='utf-8')

if __name__=='__main__':build()
