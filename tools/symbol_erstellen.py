"""Erzeugt das Programmsymbol src/kuerbis/web/kuerbis.ico (und eine PNG-Vorschau).

Aufruf: uv run python tools/symbol_erstellen.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

ZIEL = Path(__file__).resolve().parents[1] / "src" / "kuerbis" / "web"
N = 1024  # gross zeichnen, dann verkleinern (sauberes Antialiasing)

HELL = (240, 138, 44)
MITTEL = (224, 112, 31)
DUNKEL = (190, 82, 18)
STIEL = (91, 122, 42)
BLATT = (122, 158, 58)


def kuerbis() -> Image.Image:
    img = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = N / 32  # Koordinaten wie im SVG-Logo (32er Raster)

    def ellipse(cx, cy, rx, ry, farbe):
        d.ellipse([(cx - rx) * s, (cy - ry) * s, (cx + rx) * s, (cy + ry) * s], fill=farbe)

    # Stiel und Blatt
    d.line([(16 * s, 9.5 * s), (16.6 * s, 5 * s), (18.6 * s, 2.6 * s)], fill=STIEL, width=int(2.8 * s), joint="curve")
    d.ellipse([19 * s, 3.2 * s, 25.5 * s, 7 * s], fill=BLATT)

    # Körper: äussere Rippen dunkler, Mitte hell
    ellipse(9.5, 19.5, 7.8, 10, DUNKEL)
    ellipse(22.5, 19.5, 7.8, 10, DUNKEL)
    ellipse(11.5, 19.5, 7.2, 10.3, MITTEL)
    ellipse(20.5, 19.5, 7.2, 10.3, MITTEL)
    ellipse(16, 19.5, 6.2, 10.8, HELL)

    # Glanzlicht
    d.ellipse([12.6 * s, 12 * s, 14.6 * s, 17.5 * s], fill=(255, 196, 120, 170))
    return img


def main() -> None:
    gross = kuerbis()
    groessen = [16, 24, 32, 48, 64, 128, 256]
    bild256 = gross.resize((256, 256), Image.LANCZOS)
    bild256.save(ZIEL / "kuerbis.ico", sizes=[(g, g) for g in groessen])
    bild256.save(ZIEL / "kuerbis.png")
    print("geschrieben:", ZIEL / "kuerbis.ico")


if __name__ == "__main__":
    main()
