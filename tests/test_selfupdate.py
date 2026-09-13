"""
Installation par l'application elle-même (`logos/selfupdate.py`) : détection
de l'installation, extraction à côté, échange des dossiers avec retour arrière,
script d'aide Windows et nettoyage — sur de faux bundles, sans rien lancer.
"""
import os
import shutil
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from logos import selfupdate
from logos.selfupdate import Install


# --------------------------------------------------------------------------- #
#  Détection de l'installation
# --------------------------------------------------------------------------- #
def test_depuis_les_sources_rien_a_remplacer():
    assert selfupdate.current_install(frozen=False) is None
    assert selfupdate.unavailable_reason(None) is not None


def test_bundle_macos(tmp_path):
    exe = tmp_path / "Applications" / "BDA.app" / "Contents" / "MacOS" / "BDA"
    exe.parent.mkdir(parents=True)
    exe.touch()
    install = selfupdate.current_install(exe, frozen=True, system="darwin")
    assert install == Install(tmp_path / "Applications" / "BDA.app", bundle=True)
    assert install.staging.name == "BDA.app.new"
    assert install.previous.name == "BDA.app.old"


def test_macos_hors_bundle_non_pris_en_charge(tmp_path):
    exe = tmp_path / "dist" / "BDA" / "BDA"
    exe.parent.mkdir(parents=True)
    exe.touch()
    assert selfupdate.current_install(exe, frozen=True, system="darwin") is None


def test_translocation_macos_expliquee():
    root = Path("/private/var/folders/xx/T/AppTranslocation/1234-5678/d/BDA.app")
    assert selfupdate.is_translocated(root)
    reason = selfupdate.unavailable_reason(Install(root, bundle=True))
    assert reason is not None and "Finder" in reason
    assert not selfupdate.is_translocated(Path("/Applications/BDA.app"))


def test_dossier_windows(tmp_path):
    exe = tmp_path / "Programs" / "BDA" / "BDA.exe"
    exe.parent.mkdir(parents=True)
    exe.touch()
    install = selfupdate.current_install(exe, frozen=True, system="win32")
    assert install == Install(tmp_path / "Programs" / "BDA", bundle=False)


@pytest.mark.skipif(sys.platform.startswith("win"),
                    reason="chmod ne restreint pas un dossier sous Windows")
def test_dossier_parent_non_modifiable(tmp_path):
    if os.geteuid() == 0:
        pytest.skip("root écrit partout")
    parent = tmp_path / "locked"
    root = parent / "BDA"
    root.mkdir(parents=True)
    parent.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        reason = selfupdate.unavailable_reason(Install(root, bundle=False))
    finally:
        parent.chmod(stat.S_IRWXU)
    assert reason is not None and "modifiable" in reason
    assert selfupdate.unavailable_reason(Install(root, bundle=False)) is None


# --------------------------------------------------------------------------- #
#  Extraction (dossier Windows : zipfile, exécutable sur toute plateforme)
# --------------------------------------------------------------------------- #
def _folder_archive(path: Path, with_exe=True, extra=None):
    with zipfile.ZipFile(path, "w") as zf:
        if with_exe:
            zf.writestr("BDA/BDA.exe", b"nouvelle version")
        zf.writestr("BDA/_internal/lib.dll", b"lib")
        for name, data in (extra or {}).items():
            zf.writestr(name, data)


def _folder_install(tmp_path) -> Install:
    root = tmp_path / "Programs" / "BDA"
    root.mkdir(parents=True)
    (root / "BDA.exe").write_bytes(b"ancienne version")
    return Install(root, bundle=False)


def test_stage_dossier(tmp_path):
    install = _folder_install(tmp_path)
    archive = tmp_path / "BDA-9.9.9-windows.zip"
    _folder_archive(archive)
    staged = selfupdate.stage(archive, install)
    assert staged == install.staging
    assert (staged / "BDA.exe").read_bytes() == b"nouvelle version"
    assert (staged / "_internal" / "lib.dll").is_file()
    # L'ancienne n'a pas bougé et le dossier de travail est nettoyé.
    assert (install.root / "BDA.exe").read_bytes() == b"ancienne version"
    assert not (tmp_path / "Programs" / "BDA.new.extract").exists()


def test_stage_conserve_le_desinstalleur(tmp_path):
    """Posée par l'installeur, l'application porte `unins000.exe/.dat` que
    l'archive de mise à jour n'a pas : ils suivent dans la nouvelle version."""
    install = _folder_install(tmp_path)
    (install.root / "unins000.exe").write_bytes(b"uninstaller")
    (install.root / "unins000.dat").write_bytes(b"liste")
    archive = tmp_path / "BDA-9.9.9-windows.zip"
    _folder_archive(archive)
    staged = selfupdate.stage(archive, install)
    assert (staged / "unins000.exe").read_bytes() == b"uninstaller"
    assert (staged / "unins000.dat").read_bytes() == b"liste"
    assert (install.root / "unins000.exe").is_file()  # copié, pas déplacé


def test_stage_refuse_une_archive_sans_application(tmp_path):
    install = _folder_install(tmp_path)
    archive = tmp_path / "vide.zip"
    _folder_archive(archive, with_exe=False)
    with pytest.raises(selfupdate.InstallError, match="attendue"):
        selfupdate.stage(archive, install)
    assert not install.staging.exists()


def test_stage_refuse_les_chemins_remontants(tmp_path):
    install = _folder_install(tmp_path)
    archive = tmp_path / "hostile.zip"
    _folder_archive(archive, extra={"../evasion.txt": b"x"})
    with pytest.raises(selfupdate.InstallError, match="suspect"):
        selfupdate.stage(archive, install)
    assert not (tmp_path / "Programs" / "evasion.txt").exists()


def test_stage_refuse_un_fichier_qui_n_est_pas_une_archive(tmp_path):
    install = _folder_install(tmp_path)
    archive = tmp_path / "pas-un-zip.zip"
    archive.write_bytes(b"n'importe quoi")
    with pytest.raises(selfupdate.InstallError, match="extraction"):
        selfupdate.stage(archive, install)


# --------------------------------------------------------------------------- #
#  Extraction d'un bundle macOS (ditto, liens symboliques conservés)
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(shutil.which("ditto") is None, reason="ditto absent (macOS seulement)")
def test_stage_bundle_macos_conserve_les_liens(tmp_path):
    src = tmp_path / "build" / "BDA.app"
    (src / "Contents" / "MacOS").mkdir(parents=True)
    (src / "Contents" / "MacOS" / "BDA").write_bytes(b"nouvelle version")
    fw = src / "Contents" / "Frameworks" / "Qt.framework" / "Versions" / "A"
    fw.mkdir(parents=True)
    (fw / "Qt").write_bytes(b"lib")
    (fw.parent / "Current").symlink_to("A")
    archive = tmp_path / "BDA-9.9.9-macos.zip"
    subprocess.run(["ditto", "-c", "-k", "--keepParent", str(src), str(archive)], check=True)

    root = tmp_path / "Applications" / "BDA.app"
    (root / "Contents" / "MacOS").mkdir(parents=True)
    (root / "Contents" / "MacOS" / "BDA").write_bytes(b"ancienne version")
    install = Install(root, bundle=True)

    staged = selfupdate.stage(archive, install)
    assert staged == install.staging
    assert (staged / "Contents" / "MacOS" / "BDA").read_bytes() == b"nouvelle version"
    current = staged / "Contents" / "Frameworks" / "Qt.framework" / "Versions" / "Current"
    assert current.is_symlink() and os.readlink(current) == "A"


# --------------------------------------------------------------------------- #
#  Échange des dossiers
# --------------------------------------------------------------------------- #
def test_swap_conserve_l_ancienne_version(tmp_path):
    install = _folder_install(tmp_path)
    archive = tmp_path / "BDA-9.9.9-windows.zip"
    _folder_archive(archive)
    staged = selfupdate.stage(archive, install)

    selfupdate.swap(install, staged)
    assert (install.root / "BDA.exe").read_bytes() == b"nouvelle version"
    assert (install.previous / "BDA.exe").read_bytes() == b"ancienne version"
    assert not install.staging.exists()


def test_swap_remet_l_ancienne_en_place_si_le_remplacement_echoue(tmp_path):
    install = _folder_install(tmp_path)
    missing = install.staging  # jamais créé : le second renommage échoue
    with pytest.raises(selfupdate.InstallError, match="remplacement"):
        selfupdate.swap(install, missing)
    assert (install.root / "BDA.exe").read_bytes() == b"ancienne version"
    assert not install.previous.exists()


def test_cleanup_efface_les_restes(tmp_path):
    install = _folder_install(tmp_path)
    install.previous.mkdir()
    install.staging.mkdir()
    (install.root.parent / "BDA-update.cmd").write_text("rem")
    selfupdate.cleanup_previous(install)
    assert not install.previous.exists()
    assert not install.staging.exists()
    assert not (install.root.parent / "BDA-update.cmd").exists()
    assert install.root.is_dir()  # l'installation en cours, elle, reste


def test_cleanup_sans_installation_ne_fait_rien(monkeypatch):
    monkeypatch.setattr(selfupdate, "current_install", lambda: None)
    selfupdate.cleanup_previous()  # ne lève pas


# --------------------------------------------------------------------------- #
#  Windows : script d'aide
# --------------------------------------------------------------------------- #
def test_script_windows_attend_echange_et_relance():
    install = Install(Path(r"C:\Programs\BDA"), bundle=False)
    script = selfupdate.windows_helper_script(install, install.staging, pid=4242)
    assert "PID eq 4242" in script
    assert r'move "C:\Programs\BDA" "C:\Programs\BDA.old"' in script
    assert r'move "C:\Programs\BDA.new" "C:\Programs\BDA"' in script
    assert r'start "" "C:\Programs\BDA\BDA.exe"' in script
    # En cas d'échec du second déplacement, l'ancienne revient et est relancée.
    assert script.index(":rollback") < script.index(r'move "C:\Programs\BDA.old" "C:\Programs\BDA"')
    assert "\r\n" in script  # fins de ligne attendues par cmd.exe
    assert "chcp 65001" in script
    assert "reg add" not in script  # sans version, on ne touche pas au registre


def test_script_windows_met_a_jour_la_version_installee():
    """Avec la version, le script tient à jour « Applications installées » —
    après l'échange réussi et seulement si la clé de l'installeur existe."""
    install = Install(Path(r"C:\Programs\BDA"), bundle=False)
    script = selfupdate.windows_helper_script(install, install.staging, pid=1, version="1.2.3")
    stamp = next(line for line in script.split("\r\n") if "reg add" in line)
    assert stamp.startswith(f'reg query "{selfupdate.UNINSTALL_KEY}" >nul 2>&1 && reg add')
    assert '/v DisplayVersion /t REG_SZ /d "1.2.3" /f' in stamp
    swap_line = script.index(r'move "C:\Programs\BDA.new" "C:\Programs\BDA"')
    assert swap_line < script.index(stamp) < script.index(":rollback")


# --------------------------------------------------------------------------- #
#  install_and_restart : ne lance rien pendant les tests
# --------------------------------------------------------------------------- #
def test_install_and_restart_bundle(tmp_path, monkeypatch):
    root = tmp_path / "Applications" / "BDA.app"
    (root / "Contents" / "MacOS").mkdir(parents=True)
    (root / "Contents" / "MacOS" / "BDA").write_bytes(b"ancienne version")
    install = Install(root, bundle=True)
    staged = install.staging
    (staged / "Contents" / "MacOS").mkdir(parents=True)
    (staged / "Contents" / "MacOS" / "BDA").write_bytes(b"nouvelle version")

    launched = []
    monkeypatch.setattr(selfupdate.subprocess, "Popen",
                        lambda args, **kw: launched.append((args, kw)))
    selfupdate.install_and_restart(install, staged, pid=1234)

    assert (root / "Contents" / "MacOS" / "BDA").read_bytes() == b"nouvelle version"
    assert (install.previous / "Contents" / "MacOS" / "BDA").read_bytes() == b"ancienne version"
    (args, kw), = launched
    assert args[:2] == ["/bin/sh", "-c"]
    assert "kill -0 1234" in args[2] and f"'open' '-n' '{root}'" in args[2]
    assert kw["start_new_session"] is True


def test_install_and_restart_dossier_confie_au_script(tmp_path, monkeypatch):
    install = _folder_install(tmp_path)
    launched = []
    monkeypatch.setattr(selfupdate.subprocess, "Popen",
                        lambda args, **kw: launched.append(args))
    selfupdate.install_and_restart(install, install.staging, pid=99)
    # Rien n'a bougé : c'est le script, après la fin du processus, qui échange.
    assert (install.root / "BDA.exe").read_bytes() == b"ancienne version"
    script = install.root.parent / "BDA-update.cmd"
    assert script.is_file() and "PID eq 99" in script.read_text(encoding="utf-8")
    (args,) = launched
    assert args[:2] == ["cmd.exe", "/c"] and args[2] == str(script)
