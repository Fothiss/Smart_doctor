"""Генерация ассетов бренда: favicon.ico, apple-touch-icon.png, og-image.png.

Знак повторяет `public/favicon.svg` и `src/components/ui/Logo.tsx`: две скобки-«фрагмент» и
точка-источник. Скрипт не входит в сборку приложения — он нужен, чтобы иконки и картинку для
соцсетей можно было перегенерировать без графического редактора.

Запуск (из каталога frontend, нужен Pillow и сеть за начертанием Unbounded):
    python scripts/gen-brand-assets.py
"""

from __future__ import annotations

import re
import tempfile
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

PUBLIC = Path(__file__).resolve().parent.parent / "public"

BRAND = (15, 118, 110, 255)
WHITE = (255, 255, 255, 255)
DARK = (11, 18, 32, 255)
INK = (232, 238, 251, 255)
MUTED = (148, 163, 184, 255)
ACCENT = (34, 211, 238, 255)

SUPERSAMPLE = 8
STROKE = 2.2 / 32


def display_font(px: int) -> ImageFont.FreeTypeFont:
    """Начертание бренда: скачивается один раз во временный каталог."""
    cache = Path(tempfile.gettempdir()) / "smart-doctor-unbounded-600.ttf"
    if not cache.exists():
        css = urllib.request.urlopen(
            "https://fonts.googleapis.com/css2?family=Unbounded:wght@600"
        ).read().decode()
        url = re.search(r"url\((https:[^)]+\.ttf)\)", css)
        if url is None:
            raise RuntimeError("Unbounded TTF не найден в ответе Google Fonts")
        cache.write_bytes(urllib.request.urlopen(url.group(1)).read())
    return ImageFont.truetype(str(cache), px)


def draw_mark(size: int, background: tuple[int, int, int, int] | None) -> Image.Image:
    """Знак с запасом по размеру и уменьшением: так края остаются гладкими на 16px."""
    big = size * SUPERSAMPLE
    image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    if background is not None:
        draw.rounded_rectangle([0, 0, big - 1, big - 1], radius=int(big * 0.24), fill=background)

    def p(x: float, y: float) -> tuple[float, float]:
        return (x / 32 * big, y / 32 * big)

    width = max(2, int(big * STROKE))
    draw.line(
        [p(12.5, 9), p(10.2, 9), p(9, 10.2), p(9, 21.8), p(10.2, 23), p(12.5, 23)],
        fill=WHITE,
        width=width,
        joint="curve",
    )
    draw.line(
        [p(19.5, 9), p(21.8, 9), p(23, 10.2), p(23, 21.8), p(21.8, 23), p(19.5, 23)],
        fill=WHITE,
        width=width,
        joint="curve",
    )
    r = 2.6 / 32 * big
    cx, cy = p(16, 16)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=WHITE)

    return image.resize((size, size), Image.LANCZOS)


def favicon() -> None:
    icons = [draw_mark(size, BRAND) for size in (16, 32, 48, 64)]
    icons[-1].save(PUBLIC / "favicon.ico", format="ICO", sizes=[(16, 16), (32, 32), (48, 48)])
    print("favicon.ico готов")


def apple_touch() -> None:
    draw_mark(180, BRAND).convert("RGB").save(PUBLIC / "apple-touch-icon.png", format="PNG")
    print("apple-touch-icon.png готов")


def og_image() -> None:
    width, height = 1200, 630
    image = Image.new("RGB", (width, height), DARK)
    draw = ImageDraw.Draw(image, "RGBA")

    # Те же два пятна света, что и в aurora-подложке интерфейса
    draw.ellipse([-260, -320, 620, 420], fill=(34, 211, 238, 26))
    draw.ellipse([760, 300, 1500, 1000], fill=(139, 92, 246, 24))

    mark = draw_mark(104, None)
    image.paste(mark, (96, 84), mark)

    display = display_font(92)
    body = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 30)
    body_bold = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 30)

    draw.line([(98, 250), (198, 250)], fill=ACCENT, width=4)

    draw.text((96, 286), "Smart Doctor", font=display, fill=INK)
    draw.text((98, 424), "Проверка врачебных протоколов", font=body_bold, fill=INK)
    draw.text((98, 468), "на соответствие клиническим рекомендациям", font=body, fill=MUTED)
    draw.text(
        (98, 534),
        "Каждый вывод ссылается на конкретный фрагмент клинрека",
        font=body,
        fill=MUTED,
    )

    image.save(PUBLIC / "og-image.png", format="PNG")
    print("og-image.png готов")


if __name__ == "__main__":
    favicon()
    apple_touch()
    og_image()
