"""Manifeste produit par `packaging/package.py` : les archives installables."""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def package():
    spec = importlib.util.spec_from_file_location("package", ROOT / "packaging" / "package.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_manifeste_avec_archives(package, tmp_path):
    version = package.version()
    archive = tmp_path / f"BDA-{version}-macos.zip"
    archive.write_bytes(b"archive")
    package.write_checksum(archive)
    (tmp_path / f"BDA-{version}-linux.zip").write_bytes(b"x")  # sans .sha256 : ignoré ?
    (tmp_path / f"BDA-{version}-linux.zip.sha256").write_text("deadbeef  x\n")
    (tmp_path / "BDA-0.0.1-windows.zip").write_bytes(b"vieille")  # autre version : ignorée

    target = package.write_manifest(
        "https://exemple.test/releases/latest", "Notes", tmp_path,
        asset_base="https://exemple.test/releases/download/v" + version + "/",
    )
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["version"] == version and payload["notes"] == "Notes"
    assert set(payload["assets"]) == {"macos", "linux"}
    mac = payload["assets"]["macos"]
    assert mac["url"] == f"https://exemple.test/releases/download/v{version}/BDA-{version}-macos.zip"
    assert mac["sha256"] == hashlib.sha256(b"archive").hexdigest()
    assert mac["size"] == len(b"archive")


def test_manifeste_sans_asset_base_reste_ancien_format(package, tmp_path):
    target = package.write_manifest("https://exemple.test/releases/latest", "", tmp_path)
    assert "assets" not in json.loads(target.read_text(encoding="utf-8"))


def test_somme_manquante_est_une_erreur(package, tmp_path):
    (tmp_path / f"BDA-{package.version()}-macos.zip").write_bytes(b"archive")
    with pytest.raises(SystemExit):
        package.collect_assets(tmp_path, "https://exemple.test/dl")
