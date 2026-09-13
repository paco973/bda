"""
Installation d'une nouvelle version **par l'application elle-même**, puis
redémarrage — la suite de `logos/updates.py` (qui vérifie et télécharge).

Principe, identique sur les deux plateformes : l'archive vérifiée est extraite
**à côté** de l'installation en cours (`BDA.app.new` / `BDA.new`, sur le même
volume, pour que l'échange soit un simple renommage) ; l'installation en cours
est renommée en `.old`, la nouvelle prend sa place, et l'application se relance.

- macOS : un processus en cours garde ses fichiers ouverts par inode, on peut
  donc renommer le bundle sous ses pieds. L'extraction passe par `ditto`, pas
  `zipfile` : les frameworks Qt du `.app` sont faits de liens symboliques que
  `zipfile` matérialiserait en copies (bundle cassé, même piège que dans
  `packaging/package.py`).
- Windows : le dossier d'un exécutable en cours ne peut **pas** être déplacé.
  Un script `.cmd` détaché attend la fin du processus, échange les dossiers,
  puis relance `BDA.exe`.

L'ancienne version (`.old`) est conservée jusqu'au **prochain démarrage réussi**
(`cleanup_previous()`, appelé par `app.main`) : si la nouvelle refuse de se
lancer un dimanche matin, l'opérateur renomme le dossier `.old` à la main.

Pourquoi la signature de code n'est pas un prérequis : Gatekeeper et
SmartScreen ne bloquent que les fichiers marqués comme téléchargés par un
navigateur ; une archive récupérée par `urllib` ne porte pas cette marque.
L'intégrité repose donc sur HTTPS + empreinte SHA-256 (`updates.download_asset`).

Aucune dépendance Qt : la logique de fichiers est testée sur de faux bundles.
"""
import os
import shutil
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath

# Nom de l'exécutable / du bundle tel que produit par `packaging/bda.spec`.
APP_NAME = "BDA"


class InstallError(Exception):
    """Installation impossible : message destiné à l'opérateur."""


@dataclass(frozen=True)
class Install:
    """L'installation en cours : `root` est le `.app` (macOS) ou le dossier
    `BDA/` (Windows) à remplacer ; `bundle` dit lequel des deux."""
    root: Path
    bundle: bool

    @property
    def staging(self) -> Path:
        return self.root.with_name(self.root.name + ".new")

    @property
    def previous(self) -> Path:
        return self.root.with_name(self.root.name + ".old")


def current_install(executable=None, frozen=None, system=None) -> Install | None:
    """L'installation à remplacer, ou None si l'appli ne tourne pas gelée
    (depuis les sources, rien à remplacer) ou dans une disposition inconnue."""
    frozen = getattr(sys, "frozen", False) if frozen is None else frozen
    if not frozen:
        return None
    exe = Path(sys.executable if executable is None else executable).resolve()
    system = sys.platform if system is None else system
    if system == "darwin":
        # …/BDA.app/Contents/MacOS/BDA — l'archive macOS contient un `.app`,
        # une installation « en dossier » n'aurait rien de compatible à recevoir.
        if len(exe.parents) >= 3 and exe.parent.name == "MacOS" and exe.parents[2].suffix == ".app":
            return Install(exe.parents[2], bundle=True)
        return None
    if system.startswith("win"):
        return Install(exe.parent, bundle=False)
    return None


def unavailable_reason(install: Install | None) -> str | None:
    """None si l'installation intégrée est possible, sinon la raison, formulée
    pour l'opérateur (affichée dans l'infobulle du bandeau et dans « Aide →
    Rechercher les mises à jour… ») — le bandeau retombe alors sur « ouvrir
    la page de téléchargement »."""
    if install is None:
        return ("l'application ne tourne pas depuis une version installée "
                "(bundle BDA.app sur macOS, dossier BDA sur Windows)")
    if is_translocated(install.root):
        # Gatekeeper lance une application téléchargée par un navigateur, et
        # jamais déplacée, depuis un montage temporaire en lecture seule
        # (« App Translocation ») : son vrai dossier est inconnu et celui-ci
        # n'est pas modifiable. Déplacer l'application avec le Finder suffit.
        return ("macOS exécute cette application depuis un emplacement temporaire "
                "protégé, comme pour toute application téléchargée qui n'a pas encore "
                "été déplacée : glissez BDA dans le dossier Applications avec le "
                "Finder, puis relancez-la")
    parent = install.root.parent
    # Sous Windows, `os.access` ne reflète pas les ACL des dossiers : un refus
    # réel y sera rattrapé plus tard par `stage()` (InstallError, rien modifié).
    if not os.access(parent, os.W_OK):
        return (f"le dossier {parent} n'est pas modifiable par cet utilisateur "
                "(sur macOS, seul un compte administrateur peut modifier Applications)")
    return None


def is_translocated(path) -> bool:
    """Vrai si `path` est dans un montage « App Translocation » de macOS."""
    return "/AppTranslocation/" in str(path)


def _expected_executable(install: Install, root: Path) -> Path:
    if install.bundle:
        return root / "Contents" / "MacOS" / APP_NAME
    return root / f"{APP_NAME}.exe"


def stage(archive, install: Install) -> Path:
    """Extrait `archive` en `BDA.app.new` / `BDA.new` à côté de l'installation
    et renvoie ce chemin. Lève `InstallError` si l'archive n'a pas la forme
    attendue (l'exécutable doit s'y trouver là où on l'attend)."""
    archive = Path(archive)
    staging = install.staging
    _remove_tree(staging)
    parent = staging.parent
    if install.bundle:
        # `ditto -x -k` recrée les liens symboliques ; l'archive a `BDA.app`
        # comme racine (`--keepParent` côté empaquetage).
        scratch = parent / (staging.name + ".extract")
        _remove_tree(scratch)
        scratch.mkdir()
        try:
            subprocess.run(["ditto", "-x", "-k", str(archive), str(scratch)], check=True,
                           capture_output=True)
        except (OSError, subprocess.CalledProcessError) as exc:
            _remove_tree(scratch)
            raise InstallError(f"extraction impossible ({exc})") from exc
        extracted = scratch / f"{APP_NAME}.app"
    else:
        scratch = parent / (staging.name + ".extract")
        _remove_tree(scratch)
        try:
            with zipfile.ZipFile(archive) as zf:
                _check_members(zf)
                zf.extractall(scratch)
        except (OSError, zipfile.BadZipFile, InstallError) as exc:
            _remove_tree(scratch)
            raise InstallError(f"extraction impossible ({exc})") from exc
        extracted = scratch / APP_NAME

    if not _expected_executable(install, extracted).is_file():
        _remove_tree(scratch)
        raise InstallError("l'archive ne contient pas l'application attendue")
    extracted.rename(staging)
    _remove_tree(scratch)
    return staging


def _check_members(zf: zipfile.ZipFile):
    """Refuse une archive qui écrirait hors de son dossier (chemins absolus ou
    remontants) : le contenu distant n'est pas digne de confiance."""
    for name in zf.namelist():
        path = Path(name)
        if path.is_absolute() or ".." in path.parts:
            raise InstallError(f"chemin suspect dans l'archive : {name}")


def swap(install: Install, staged: Path):
    """Met la version extraite à la place de l'installation en cours (macOS,
    ou test) : `root` -> `root.old`, `staged` -> `root`. Sur échec de la
    seconde étape, remet l'ancienne en place pour ne jamais laisser le poste
    sans application."""
    _remove_tree(install.previous)
    install.root.rename(install.previous)
    try:
        staged.rename(install.root)
    except OSError as exc:
        install.previous.rename(install.root)
        raise InstallError(f"remplacement impossible ({exc})") from exc


def install_and_restart(install: Install, staged: Path, pid=None):
    """Applique la mise à jour et programme le redémarrage ; l'appelant doit
    ensuite **quitter** l'application. Lève `InstallError` si rien n'a été
    modifié ; une fois cette fonction revenue, l'échange est fait (macOS) ou
    confié au script d'aide (Windows)."""
    pid = os.getpid() if pid is None else pid
    if install.bundle:
        swap(install, staged)
        _relaunch_after_exit_posix(pid, ["open", "-n", str(install.root)])
    else:
        _relaunch_windows(install, staged, pid)


def _relaunch_after_exit_posix(pid, command):
    """Attend la fin de ce processus puis lance `command` — détaché, pour que
    la nouvelle instance ne se batte pas avec l'ancienne pour la base SQLite."""
    quoted = " ".join(_sh_quote(part) for part in command)
    script = f"while kill -0 {int(pid)} 2>/dev/null; do sleep 0.2; done; {quoted}"
    try:
        subprocess.Popen(["/bin/sh", "-c", script], start_new_session=True,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    except OSError as exc:
        raise InstallError(
            f"la nouvelle version est installée mais le redémarrage a échoué ({exc}) : "
            "relancez l'application à la main"
        ) from exc


def _sh_quote(text: str) -> str:
    return "'" + str(text).replace("'", "'\"'\"'") + "'"


def windows_helper_script(install: Install, staged: Path, pid: int) -> str:
    """Script `.cmd` qui attend la fin du processus, échange les dossiers puis
    relance l'application. Séparé de son lancement pour être testable (sur
    toute plateforme : les chemins sont mis en forme façon Windows). Écrit en
    UTF-8 avec `chcp 65001` : un nom d'utilisateur accentué dans le chemin ne
    doit pas casser le script."""
    root = PureWindowsPath(str(install.root))
    previous = PureWindowsPath(str(install.previous))
    staged = PureWindowsPath(str(staged))
    exe = root / f"{APP_NAME}.exe"
    return "\r\n".join([
        "@echo off",
        "chcp 65001 >nul",
        ":wait",
        f'tasklist /FI "PID eq {int(pid)}" 2>nul | find "{int(pid)}" >nul',
        "if not errorlevel 1 (",
        "  timeout /t 1 /nobreak >nul",
        "  goto wait",
        ")",
        f'if exist "{previous}" rmdir /s /q "{previous}"',
        f'move "{root}" "{previous}" >nul || goto failed',
        f'move "{staged}" "{root}" >nul || goto rollback',
        f'start "" "{exe}"',
        "exit /b 0",
        ":rollback",
        f'move "{previous}" "{root}" >nul',
        ":failed",
        f'start "" "{exe}"',
        "exit /b 1",
        "",
    ])


def _relaunch_windows(install: Install, staged: Path, pid: int):
    script_path = install.root.parent / f"{APP_NAME}-update.cmd"
    try:
        script_path.write_text(windows_helper_script(install, staged, pid), encoding="utf-8")
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        subprocess.Popen(["cmd.exe", "/c", str(script_path)], creationflags=flags,
                         close_fds=True, stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as exc:
        raise InstallError(f"impossible de lancer l'installation ({exc})") from exc


def cleanup_previous(install: Install | None = None):
    """Au démarrage : supprime la version précédente (`.old`), le dossier
    d'extraction et le script d'aide laissés par une mise à jour réussie.
    Silencieux : un échec ici ne doit jamais empêcher l'appli de s'ouvrir."""
    if install is None:
        install = current_install()
    if install is None:
        return
    for leftover in (install.previous, install.staging,
                     install.staging.with_name(install.staging.name + ".extract")):
        _remove_tree(leftover)
    try:
        (install.root.parent / f"{APP_NAME}-update.cmd").unlink(missing_ok=True)
    except OSError:
        pass


def _remove_tree(path: Path):
    try:
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
    except OSError:
        pass
