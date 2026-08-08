"""
Génère les icônes d'application (.icns pour macOS, .ico pour Windows) à partir
de `logos/assets/logo.png`.

À relancer uniquement si le logo change :

    python packaging/make_icons.py

Aucune dépendance supplémentaire : le redimensionnement passe par Qt (déjà
requis par l'application) et les deux conteneurs (.icns et .ico) acceptent des
images PNG telles quelles, écrites ici à la main.
"""
import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, Qt
from PySide6.QtGui import QGuiApplication, QImage

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "logos" / "assets" / "logo.png"
ICONS_DIR = Path(__file__).resolve().parent / "icons"

# Types de chunks ICNS reconnus par macOS, associés à la taille en pixels.
ICNS_TYPES = {
    b"ic07": 128, b"ic08": 256, b"ic09": 512, b"ic10": 1024,
    b"ic11": 32, b"ic12": 64, b"ic13": 256, b"ic14": 512,
}
# Tailles embarquées dans le .ico Windows (16 à 256).
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)


def png_bytes(image: QImage, size: int) -> bytes:
    """Le logo redimensionné en `size`x`size`, encodé en PNG."""
    scaled = image.scaled(
        size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation
    ).convertToFormat(QImage.Format_RGBA8888)
    buffer = QBuffer()  # tampon interne : ne pas lui passer un QByteArray temporaire
    buffer.open(QBuffer.WriteOnly)
    scaled.save(buffer, "PNG")
    return bytes(buffer.data())


def write_icns(image: QImage, target: Path):
    """Conteneur ICNS : magie « icns », taille totale, puis un chunk par taille."""
    chunks = b""
    for chunk_type, size in ICNS_TYPES.items():
        data = png_bytes(image, size)
        chunks += chunk_type + struct.pack(">I", len(data) + 8) + data
    target.write_bytes(b"icns" + struct.pack(">I", len(chunks) + 8) + chunks)


def write_ico(image: QImage, target: Path):
    """Conteneur ICO : en-tête, un descripteur par taille, puis les PNG."""
    images = [png_bytes(image, size) for size in ICO_SIZES]
    header = struct.pack("<HHH", 0, 1, len(images))  # réservé, type 1 = icône
    offset = len(header) + 16 * len(images)
    entries = b""
    for size, data in zip(ICO_SIZES, images):
        # 0 signifie 256 dans les champs largeur/hauteur (codés sur un octet).
        entries += struct.pack(
            "<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(data), offset
        )
        offset += len(data)
    target.write_bytes(header + entries + b"".join(images))


def main():
    if not SOURCE.exists():
        sys.exit(f"Logo introuvable : {SOURCE}")
    QGuiApplication(sys.argv)  # requis par Qt pour charger/encoder les images
    image = QImage(str(SOURCE))
    if image.isNull():
        sys.exit(f"Logo illisible : {SOURCE}")
    ICONS_DIR.mkdir(parents=True, exist_ok=True)
    write_icns(image, ICONS_DIR / "bda.icns")
    write_ico(image, ICONS_DIR / "bda.ico")
    print(f"Icônes écrites dans {ICONS_DIR}")


if __name__ == "__main__":
    main()
