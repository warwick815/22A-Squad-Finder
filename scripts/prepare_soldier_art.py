"""Turn new soldier artwork into the website's cut-out images.

Put 24 images in one folder, named <role>-<stage>.png (or .jpg/.webp):
roles: rifle medic crew recon at lmg pilot engineer; stages: 0 1 2.
Then run:  python scripts/prepare_soldier_art.py path/to/folder
Backgrounds are removed (needs `pip install rembg onnxruntime`) and each
image is saved as web/soldiers/<role>-<stage>.webp at 444x592.
"""
import sys
from pathlib import Path
from PIL import Image

ROLES = ('rifle', 'medic', 'crew', 'recon', 'at', 'lmg', 'pilot', 'engineer')
OUT = Path(__file__).resolve().parent.parent / 'web' / 'soldiers'
SIZE = (444, 592)


def fit(image):
    """Trim empty space and centre the figure on a 3:4 canvas, feet at the bottom."""
    box = image.getchannel('A').point(lambda v: 255 if v > 30 else 0).getbbox()
    if box:
        image = image.crop(box)
    scale = min(SIZE[0] / image.width, SIZE[1] / image.height) * 0.96
    image = image.resize((max(1, round(image.width * scale)), max(1, round(image.height * scale))), Image.LANCZOS)
    canvas = Image.new('RGBA', SIZE, (0, 0, 0, 0))
    canvas.paste(image, ((SIZE[0] - image.width) // 2, SIZE[1] - image.height), image)
    return canvas


def main(folder):
    from rembg import remove, new_session
    session = new_session('isnet-general-use')
    done = 0
    for role in ROLES:
        for stage in range(3):
            source = next((p for ext in ('png', 'jpg', 'jpeg', 'webp') for p in [Path(folder) / f'{role}-{stage}.{ext}'] if p.exists()), None)
            if not source:
                print(f'missing {role}-{stage}; keeping the current image')
                continue
            image = Image.open(source).convert('RGBA')
            if image.getchannel('A').getextrema()[0] == 255:  # no transparency yet
                image = remove(image, session=session, post_process_mask=True)
            fit(image).save(OUT / f'{role}-{stage}.webp', 'WEBP', quality=82, method=6)
            done += 1
    print(f'{done} image(s) written to {OUT}')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
