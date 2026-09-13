"""
Met en forme le résultat de PyInstaller pour la distribution : une archive
versionnée, sa somme de contrôle, et le manifeste lu par le vérificateur de
version (`logos/updates.py`).

    pyinstaller --noconfirm --clean packaging/bda.spec
    python packaging/package.py

Produit dans `dist/` :

    BDA-<version>-<plateforme>.zip
    BDA-<version>-<plateforme>.zip.sha256

et, sur Windows, si le compilateur d'Inno Setup est trouvé (chemin par défaut
d'Inno Setup 6 ou variable d'environnement `ISCC`), l'installeur décrit par
`packaging/bda.iss` :

    BDA-<version>-windows-setup.exe
    BDA-<version>-windows-setup.exe.sha256

L'archive reste produite à côté : c'est elle que la mise à jour intégrée
télécharge, l'installeur servant à la première installation.

Sur macOS l'archive est faite avec `ditto`, et non avec `zip` : un bundle `.app`
contient des liens symboliques (frameworks Qt) que `zip` aplatit, ce qui donne
une application cassée à l'arrivée.

Le manifeste se génère à part, une fois les deux plateformes construites, en
lisant les archives et leurs sommes déposées dans `--out` :

    python packaging/package.py --manifest-only --out artifacts \\
        --release-url https://github.com/<compte>/<depot>/releases/latest \\
        --asset-base https://github.com/<compte>/<depot>/releases/download/v1.1.0

Il porte, par plateforme, l'URL directe de l'archive, sa taille et son
empreinte : c'est ce qui permet à l'application de se mettre à jour seule
(`logos/selfupdate.py`), l'empreinte étant vérifiée avant toute installation.
"""
import argparse
import hashlib
import json
import os
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


# Compilateur d'Inno Setup : chemin d'installation par défaut sur Windows, ou
# celui donné par la variable d'environnement ISCC (autre version, autre dossier).
DEFAULT_ISCC = Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe")


def installer_name(version_: str | None = None) -> str:
    return f"BDA-{version_ or version()}-windows-setup.exe"


def find_iscc(environ=None) -> Path | None:
    """Le compilateur d'Inno Setup s'il est disponible (Windows seulement)."""
    environ = os.environ if environ is None else environ
    candidate = environ.get("ISCC")
    if candidate:
        path = Path(candidate)
        return path if path.is_file() else None
    if platform.system() != "Windows":
        return None
    return DEFAULT_ISCC if DEFAULT_ISCC.is_file() else None


def installer_command(iscc: Path, version_: str, source: Path, out_dir: Path) -> list:
    """Ligne de commande ISCC : la version vient de `logos/version.py`, le
    dossier PyInstaller et la sortie sont passés au script pour ne dépendre
    d'aucun chemin relatif au moment de la compilation."""
    return [
        str(iscc),
        f"/DAppVersion={version_}",
        f"/DSourceDir={source}",
        f"/DOutputDir={out_dir}",
        str(ROOT / "packaging" / "bda.iss"),
    ]


def build_installer() -> Path | None:
    """Compile l'installeur Windows depuis `dist/BDA/`, ou None si ISCC est absent."""
    iscc = find_iscc()
    if iscc is None:
        return None
    folder = DIST / "BDA"
    if not folder.is_dir():
        sys.exit("Rien à installer : lancer d'abord pyinstaller packaging/bda.spec")
    target = DIST / installer_name()
    target.unlink(missing_ok=True)
    subprocess.run(installer_command(iscc, version(), folder, DIST), check=True)
    if not target.is_file():
        sys.exit(f"ISCC n'a pas produit {target.name}")
    return target


def collect_assets(out_dir: Path, asset_base: str) -> dict:
    """Entrée `assets` du manifeste : pour chaque `BDA-<version>-<plateforme>.zip`
    présent dans `out_dir`, l'URL sous `asset_base`, la taille et l'empreinte
    lue dans le `.sha256` voisin (celle que le téléchargeur vérifiera)."""
    assets = {}
    pattern = re.compile(rf"^BDA-{re.escape(version())}-(?P<tag>[a-z]+)\.zip$")
    for archive in sorted(out_dir.glob("*.zip")):
        match = pattern.match(archive.name)
        if not match:
            continue
        checksum = archive.with_suffix(archive.suffix + ".sha256")
        if not checksum.is_file():
            sys.exit(f"Somme manquante pour {archive.name} : {checksum.name}")
        digest = checksum.read_text(encoding="utf-8").split()[0].lower()
        assets[match.group("tag")] = {
            "url": f"{asset_base.rstrip('/')}/{archive.name}",
            "sha256": digest,
            "size": archive.stat().st_size,
        }
    return assets


def write_manifest(release_url: str, notes: str, out_dir: Path, asset_base=None) -> Path:
    """Manifeste consommé par `logos.updates` : version publiée, page où la
    récupérer (repli navigateur) et, si `asset_base` est donné, les archives
    installables par l'application elle-même."""
    if not release_url.startswith("https://"):
        sys.exit("--release-url doit être en HTTPS (exigé par logos/updates.py)")
    if asset_base and not asset_base.startswith("https://"):
        sys.exit("--asset-base doit être en HTTPS (exigé par logos/updates.py)")
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {"version": version(), "url": release_url, "notes": notes}
    if asset_base:
        payload["assets"] = collect_assets(out_dir, asset_base)
        if not payload["assets"]:
            sys.exit(f"Aucune archive BDA-{version()}-*.zip dans {out_dir}")
    target = out_dir / "latest.json"
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest-only", action="store_true",
        help="n'écrire que latest.json (aucun build requis)",
    )
    parser.add_argument("--release-url", help="page de téléchargement (HTTPS)")
    parser.add_argument(
        "--asset-base",
        help="préfixe HTTPS des archives (ex. …/releases/download/v1.1.0) : "
             "renseigne les archives installables par l'application",
    )
    parser.add_argument("--notes", default="", help="notes de version affichées")
    parser.add_argument(
        "--out", type=Path, default=DIST, help="dossier de sortie du manifeste",
    )
    args = parser.parse_args()

    if args.manifest_only:
        if not args.release_url:
            sys.exit("--manifest-only exige --release-url")
        print(f"Écrit : {write_manifest(args.release_url, args.notes, args.out, args.asset_base)}")
        return

    archive = build_archive()
    checksum = write_checksum(archive)
    size_mb = archive.stat().st_size / 1_000_000
    print(f"Écrit : {archive} ({size_mb:.0f} Mo)")
    print(f"Écrit : {checksum}")
    if platform_tag() == "windows":
        installer = build_installer()
        if installer is None:
            print("Inno Setup introuvable : pas d'installeur (archive seule). "
                  "Installer Inno Setup 6 ou renseigner ISCC.")
        else:
            print(f"Écrit : {installer} ({installer.stat().st_size / 1_000_000:.0f} Mo)")
            print(f"Écrit : {write_checksum(installer)}")
    if args.release_url:
        print(f"Écrit : {write_manifest(args.release_url, args.notes, args.out, args.asset_base)}")


if __name__ == "__main__":
    main()
