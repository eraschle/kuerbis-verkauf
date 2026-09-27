"""Erzeugt anleitung.pdf aus anleitung.html.

Aufruf (im Ordner anleitung):  uv run --no-project --with xhtml2pdf python pdf_erstellen.py
"""

from pathlib import Path

from xhtml2pdf import pisa

ORDNER = Path(__file__).resolve().parent
html = (ORDNER / "anleitung.html").read_text(encoding="utf-8")
# Die PDF-Standardschrift kennt diese Zeichen nicht
html = html.replace("→", "›").replace(" ▾", "")
# xhtml2pdf rechnet Abstände anders als ein Browser: eigene, kompakte Druckformate
DRUCK = """<style>
body { font-size: 10.5pt; line-height: 1.35; padding: 0; }
h1 { font-size: 22pt; }
h2 { font-size: 14pt; margin-top: 14pt; margin-bottom: 4pt; }
h3 { font-size: 11.5pt; margin-top: 8pt; margin-bottom: 2pt; }
p { margin: 0 0 4pt 0; }
li { margin: 0; }
ol, ul { margin-top: 0; margin-bottom: 4pt; }
.untertitel { margin-bottom: 10pt; }
.download, .hinweis, .achtung { margin: 6pt 0; padding: 5pt 8pt; }
.inhalt li { margin: 0; }
figure { display: block; margin: 6pt 0; }
figure img { width: 8cm; }
figure img.breit { width: 15cm; }
figcaption { display: block; }
</style></head>"""
html = html.replace("</head>", DRUCK, 1).replace("<figure>", "<div class=\"bild\">").replace("</figure>", "</div>")
html = html.replace('<img src', '<img width="230" src').replace('<img class="breit" src', '<img width="440" src')
html = html.replace("<figcaption>", "<p class=\"bu\">").replace("</figcaption>", "</p>")
html = html.replace("</style></head>", ".bild { text-align: center; margin: 6pt 0; } .bu { font-size: 9pt; color: #6b6158; text-align: center; }</style></head>", 1)
with open(ORDNER / "anleitung.pdf", "wb") as ziel:
    ergebnis = pisa.CreatePDF(html, dest=ziel, path=str(ORDNER / "anleitung.html"), encoding="utf-8")
if ergebnis.err:
    raise SystemExit(f"PDF konnte nicht erstellt werden ({ergebnis.err} Fehler).")
print("anleitung.pdf erstellt")
