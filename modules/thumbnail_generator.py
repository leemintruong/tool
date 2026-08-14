from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageEnhance


def create_thumbnail(background_path: str, text: str, out_path: str, size=(1280, 720)) -> str:
    img = Image.open(background_path).convert("RGB")
    img.thumbnail(size, Image.LANCZOS)
    canvas = Image.new("RGB", size, (20, 20, 20))
    x = (size[0] - img.width) // 2
    y = (size[1] - img.height) // 2
    canvas.paste(img, (x, y))

    # Darken slightly for text readability.
    canvas = ImageEnhance.Brightness(canvas).enhance(0.72)
    draw = ImageDraw.Draw(canvas)

    try:
        font = ImageFont.truetype("arial.ttf", 96)
    except Exception:
        font = ImageFont.load_default()

    text = text.upper().strip()[:32]
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = (size[0] - tw) // 2
    ty = size[1] - th - 80

    # Stroke by drawing offsets.
    for ox in range(-4, 5):
        for oy in range(-4, 5):
            if ox != 0 or oy != 0:
                draw.text((tx + ox, ty + oy), text, font=font, fill=(0, 0, 0))
    draw.text((tx, ty), text, font=font, fill=(255, 255, 255))

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, quality=92)
    return out_path
