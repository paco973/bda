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


def test_installeur_ligne_de_commande(package, tmp_path):
    iscc = tmp_path / "ISCC.exe"
    command = package.installer_command(iscc, "1.2.3", tmp_path / "dist" / "BDA", tmp_path / "dist")
    assert command[0] == str(iscc)
    assert "/DAppVersion=1.2.3" in command
    assert f"/DSourceDir={tmp_path / 'dist' / 'BDA'}" in command
    assert f"/DOutputDir={tmp_path / 'dist'}" in command
    assert command[-1] == str(ROOT / "packaging" / "bda.iss")
    assert package.installer_name("1.2.3") == "BDA-1.2.3-windows-setup.exe"


def test_iscc_via_variable_d_environnement(package, tmp_path):
    iscc = tmp_path / "ISCC.exe"
    assert package.find_iscc({"ISCC": str(iscc)}) is None       # fichier absent
    iscc.write_bytes(b"")
    assert package.find_iscc({"ISCC": str(iscc)}) == iscc


def test_script_inno_coherent_avec_le_code(package):
    """L'AppId du script et celui de `selfupdate` doivent rester identiques, et
    le nom de sortie celui que `package.py` attend."""
    from logos import selfupdate

    script = (ROOT / "packaging" / "bda.iss").read_text(encoding="utf-8")
    assert f"AppId={selfupdate.INNO_APP_ID}" in script
    assert "OutputBaseFilename=BDA-{#AppVersion}-windows-setup" in script
    assert "PrivilegesRequired=lowest" in script  # la mise à jour intégrée en dépend
