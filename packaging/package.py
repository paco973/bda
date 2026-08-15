"""
Met en forme le résultat de PyInstaller pour la distribution : une archive
versionnée, sa somme de contrôle, et le manifeste lu par le vérificateur de
version (`logos/updates.py`).

    pyinstaller --noconfirm --clean packaging/bda.spec
    python packaging/package.py

Produit dans `dist/` :

    BDA-<version>-<plateforme>.zip
    BDA-<version>-<plateforme>.zip.sha256

Sur macOS l'archive est faite avec `ditto`, et non avec `zip` : un bundle `.app`
contient des liens symboliques (frameworks Qt) que `zip` aplatit, ce qui donne
une application cassée à l'arrivée.

Le manifeste se génère à part, une fois les deux plateformes construites :

    python packaging/package.py --manifest-only \\
        --release-url https://github.com/<compte>/<depot>/releases/latest
"""
import argparse
import hashlib
import json
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"


def version() -> str:
    """Version lue dans `logos/version.py` (source unique), sans importer Qt."""
    text = (ROOT / "logos" / "version.py").read_text(encoding="utf-8")
    return re.search(r'__version__\s*=\s*"([^"]+)"', text).group(1)


def platform_tag() -> str:
    return {"Darwin": "macos", "Windows": "windows"}.get(platform.system(), "linux")


def write_checksum(archive: Path) -> Path:
    """Somme SHA-256 au format `shasum -a 256` / `sha256sum`, pour que le
    téléchargeur puisse vérifier l'archive avec l'outil de son système."""
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    target = archive.with_suffix(archive.suffix + ".sha256")
    target.write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
    return target


def build_archive() -> Path:
    """Archive le livrable produit par PyInstaller pour la plateforme courante."""
    archive = DIST / f"BDA-{version()}-{platform_tag()}.zip"
    archive.unlink(missing_ok=True)

    app_bundle = DIST / "BDA.app"
    if app_bundle.is_dir():
        # `--keepParent` conserve « BDA.app » comme racine dans l'archive.
        subprocess.run(
            ["ditto", "-c", "-k", "--keepParent", str(app_bundle), str(archive)],
            check=True,
        )
        return archive

    folder = DIST / "BDA"
    if not folder.is_dir():
        sys.exit("Rien à empaqueter : lancer d'abord pyinstaller packaging/bda.spec")
    # Le dossier entier est le livrable : l'exécutable seul ne fonctionne pas.
    shutil.make_archive(str(archive.with_suffix("")), "zip", root_dir=DIST, base_dir="BDA")
    return archive


def write_manifest(release_url: str, notes: str, out_dir: Path) -> Path:
    """Manifeste consommé par `logos.updates` : version publiée et page où la
    récupérer (une page, pas un fichier : l'utilisateur choisit sa plateforme)."""
    if not release_url.startswith("https://"):
        sys.exit("--release-url doit être en HTTPS (exigé par logos/updates.py)")
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "latest.json"
    target.write_text(
        json.dumps(
            {"version": version(), "url": release_url, "notes": notes},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest-only", action="store_true",
        help="n'écrire que latest.json (aucun build requis)",
    )
    parser.add_argument("--release-url", help="page de téléchargement (HTTPS)")
    parser.add_argument("--notes", default="", help="notes de version affichées")
    parser.add_argument(
        "--out", type=Path, default=DIST, help="dossier de sortie du manifeste",
    )
    args = parser.parse_args()

    if args.manifest_only:
        if not args.release_url:
            sys.exit("--manifest-only exige --release-url")
        print(f"Écrit : {write_manifest(args.release_url, args.notes, args.out)}")
        return

    archive = build_archive()
    checksum = write_checksum(archive)
    size_mb = archive.stat().st_size / 1_000_000
    print(f"Écrit : {archive} ({size_mb:.0f} Mo)")
    print(f"Écrit : {checksum}")
    if args.release_url:
        print(f"Écrit : {write_manifest(args.release_url, args.notes, args.out)}")


if __name__ == "__main__":
    main()
