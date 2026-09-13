"""
Vérification de version : comparaison des numéros et lecture du manifeste.

Aucun accès réseau réel — `urlopen` est remplacé par un faux, et l'on vérifie
surtout que **rien ne lève** et que les réponses hostiles sont rejetées.
"""
import io
import json
import urllib.error

import pytest

from logos import updates

MANIFEST_URL = "https://exemple.test/latest.json"


class _FakeResponse(io.BytesIO):
    """Réponse HTTP minimale utilisable comme gestionnaire de contexte."""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


@pytest.fixture
def fake_manifest(monkeypatch):
    """Fait répondre `urlopen` avec le contenu donné (bytes ou exception)."""

    def install(payload):
        def fake_urlopen(url, timeout=None, context=None):
            if isinstance(payload, Exception):
                raise payload
            raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
            return _FakeResponse(raw)

        monkeypatch.setattr(updates.urllib.request, "urlopen", fake_urlopen)

    return install


# --------------------------------------------------------------------------- #
#  Comparaison de versions
# --------------------------------------------------------------------------- #
def test_parse_version():
    assert updates.parse_version("1.2.3") == (1, 2, 3)
    assert updates.parse_version("v1.2") == (1, 2)
    assert updates.parse_version("") == ()
    assert updates.parse_version("abc") == ()


def test_is_newer_compare_champ_par_champ():
    assert updates.is_newer("1.1.0", "1.0.0")
    # Comparaison numérique, pas alphabétique : 10 > 9.
    assert updates.is_newer("1.10.0", "1.9.0")
    assert not updates.is_newer("1.0.0", "1.0.0")
    assert not updates.is_newer("0.9.0", "1.0.0")


def test_is_newer_completes_par_des_zeros():
    assert not updates.is_newer("1.2", "1.2.0")
    assert updates.is_newer("1.2.1", "1.2")


def test_is_newer_refuse_une_version_illisible():
    assert not updates.is_newer("", "1.0.0")
    assert not updates.is_newer("bientôt", "1.0.0")


# --------------------------------------------------------------------------- #
#  Lecture du manifeste
# --------------------------------------------------------------------------- #
def test_desactive_sans_url_configuree():
    assert updates.check_for_update("", "1.0.0").status == updates.DISABLED


def test_desactive_si_url_non_https():
    # http en clair, file://… : on ne tente même pas la requête.
    assert updates.check_for_update("http://exemple.test/l.json").status == updates.DISABLED
    assert updates.check_for_update("file:///etc/passwd").status == updates.DISABLED


def test_version_plus_recente_detectee(fake_manifest):
    fake_manifest({"version": "1.1.0", "url": "https://exemple.test/BDA.zip",
                   "notes": "Corrections."})
    result = updates.check_for_update(MANIFEST_URL, "1.0.0")
    assert result.status == updates.AVAILABLE
    assert result.release.version == "1.1.0"
    assert result.release.notes == "Corrections."


def test_deja_a_jour(fake_manifest):
    fake_manifest({"version": "1.0.0", "url": "https://exemple.test/BDA.zip"})
    assert updates.check_for_update(MANIFEST_URL, "1.0.0").status == updates.UP_TO_DATE


def test_erreur_reseau_ne_leve_pas(fake_manifest):
    fake_manifest(urllib.error.URLError("pas de réseau"))
    assert updates.check_for_update(MANIFEST_URL, "1.0.0").status == updates.ERROR


def test_404_distingue_de_la_panne_reseau(fake_manifest):
    """Cas courant tant qu'aucune release n'est publiée : le serveur répond,
    c'est le manifeste qui manque. Le dire précisément évite de faire croire
    à une panne."""
    fake_manifest(urllib.error.HTTPError(MANIFEST_URL, 404, "Not Found", {}, None))
    assert updates.check_for_update(MANIFEST_URL, "1.0.0").status == updates.NOT_PUBLISHED


def test_autre_erreur_http_reste_une_erreur(fake_manifest):
    fake_manifest(urllib.error.HTTPError(MANIFEST_URL, 500, "Server Error", {}, None))
    assert updates.check_for_update(MANIFEST_URL, "1.0.0").status == updates.ERROR


def test_reponse_illisible(fake_manifest):
    fake_manifest(b"<html>page d'erreur</html>")
    assert updates.check_for_update(MANIFEST_URL, "1.0.0").status == updates.ERROR


def test_reponse_trop_grosse_rejetee(fake_manifest):
    fake_manifest(b"x" * (updates.MAX_RESPONSE_BYTES + 10))
    assert updates.check_for_update(MANIFEST_URL, "1.0.0").status == updates.ERROR


def test_lien_de_telechargement_non_https_rejete(fake_manifest):
    # Une nouvelle version annoncée avec un lien qu'on refuserait d'ouvrir.
    fake_manifest({"version": "9.9.9", "url": "file:///Applications/Malveillant.app"})
    assert updates.check_for_update(MANIFEST_URL, "1.0.0").status == updates.ERROR


def test_notes_tronquees(fake_manifest):
    fake_manifest({"version": "2.0.0", "url": "https://exemple.test/BDA.zip",
                   "notes": "a" * (updates.MAX_NOTES_CHARS + 100)})
    result = updates.check_for_update(MANIFEST_URL, "1.0.0")
    assert len(result.release.notes) == updates.MAX_NOTES_CHARS


def test_manifeste_non_dictionnaire(fake_manifest):
    fake_manifest(b'["1.1.0"]')
    assert updates.check_for_update(MANIFEST_URL, "1.0.0").status == updates.ERROR


# --------------------------------------------------------------------------- #
#  Archives installables (`assets` du manifeste)
# --------------------------------------------------------------------------- #
SHA = "a" * 64


def _manifest(**assets):
    return {"version": "1.1.0", "url": "https://exemple.test/releases", "assets": assets}


def test_asset_de_la_plateforme(fake_manifest):
    fake_manifest(_manifest(
        macos={"url": "https://exemple.test/BDA-1.1.0-macos.zip", "sha256": SHA.upper(), "size": 10},
        windows={"url": "https://exemple.test/BDA-1.1.0-windows.zip", "sha256": SHA, "size": 20},
    ))
    mac = updates.check_for_update(MANIFEST_URL, "1.0.0", system="Darwin").release.asset
    win = updates.check_for_update(MANIFEST_URL, "1.0.0", system="Windows").release.asset
    assert mac == updates.Asset("https://exemple.test/BDA-1.1.0-macos.zip", SHA, 10)
    assert mac.filename == "BDA-1.1.0-macos.zip"
    assert win.size == 20
    # Plateforme absente du manifeste : version annoncée, sans archive.
    assert updates.check_for_update(MANIFEST_URL, "1.0.0", system="Linux").release.asset is None


def test_manifeste_ancien_format_reste_valide(fake_manifest):
    fake_manifest({"version": "1.1.0", "url": "https://exemple.test/releases"})
    result = updates.check_for_update(MANIFEST_URL, "1.0.0")
    assert result.status == updates.AVAILABLE and result.release.asset is None


@pytest.mark.parametrize("entry", [
    {"url": "http://exemple.test/BDA.zip", "sha256": SHA, "size": 10},   # pas HTTPS
    {"url": "https://exemple.test/BDA.zip", "sha256": "abc", "size": 10},  # empreinte
    {"url": "https://exemple.test/BDA.zip", "sha256": SHA, "size": 0},
    {"url": "https://exemple.test/BDA.zip", "sha256": SHA, "size": "10"},
    {"url": "https://exemple.test/BDA.zip", "sha256": SHA, "size": True},
    {"url": "https://exemple.test/BDA.zip", "sha256": SHA,
     "size": updates.MAX_ARCHIVE_BYTES + 1},
    "pas un objet",
])
def test_asset_inexploitable_ignore_sans_bloquer(fake_manifest, entry):
    fake_manifest(_manifest(macos=entry))
    result = updates.check_for_update(MANIFEST_URL, "1.0.0", system="Darwin")
    assert result.status == updates.AVAILABLE and result.release.asset is None


# --------------------------------------------------------------------------- #
#  Téléchargement vérifié
# --------------------------------------------------------------------------- #
import hashlib


class _StreamResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


@pytest.fixture
def fake_download(monkeypatch):
    """Fait servir `payload` par `urlopen`, par blocs (comme le réseau)."""
    def install(payload):
        def fake_urlopen(url, timeout=None, context=None):
            if isinstance(payload, Exception):
                raise payload
            return _StreamResponse(payload)
        monkeypatch.setattr(updates.urllib.request, "urlopen", fake_urlopen)
    return install


def _asset(payload, **overrides):
    fields = {"url": "https://exemple.test/BDA-1.1.0-macos.zip",
              "sha256": hashlib.sha256(payload).hexdigest(), "size": len(payload)}
    fields.update(overrides)
    return updates.Asset(**fields)


def test_telechargement_verifie(tmp_path, fake_download, monkeypatch):
    monkeypatch.setattr(updates, "DOWNLOAD_CHUNK_BYTES", 4)
    payload = b"archive de test"
    fake_download(payload)
    seen = []
    path = updates.download_asset(_asset(payload), tmp_path / "updates",
                                  on_progress=lambda got, total: seen.append((got, total)))
    assert path == tmp_path / "updates" / "BDA-1.1.0-macos.zip"
    assert path.read_bytes() == payload
    assert seen[-1] == (len(payload), len(payload)) and len(seen) == 4
    assert not list(tmp_path.glob("updates/*.part"))


def test_empreinte_fausse_supprime_l_archive(tmp_path, fake_download):
    payload = b"archive de test"
    fake_download(payload)
    with pytest.raises(updates.DownloadError, match="empreinte"):
        updates.download_asset(_asset(payload, sha256="b" * 64), tmp_path)
    assert not list(tmp_path.iterdir())


def test_taille_annoncee_fausse(tmp_path, fake_download):
    payload = b"archive de test"
    fake_download(payload)
    with pytest.raises(updates.DownloadError, match="incomplète"):
        updates.download_asset(_asset(payload, size=len(payload) + 1), tmp_path)
    with pytest.raises(updates.DownloadError, match="plus grosse"):
        updates.download_asset(_asset(payload, size=len(payload) - 1), tmp_path)
    assert not list(tmp_path.iterdir())


def test_annulation_ne_laisse_rien(tmp_path, fake_download):
    payload = b"archive de test"
    fake_download(payload)
    assert updates.download_asset(_asset(payload), tmp_path, should_stop=lambda: True) is None
    assert not list(tmp_path.iterdir())


def test_panne_reseau_pendant_le_telechargement(tmp_path, fake_download):
    fake_download(urllib.error.URLError("coupure"))
    with pytest.raises(updates.DownloadError, match="interrompu"):
        updates.download_asset(_asset(b"x"), tmp_path)


def test_lien_non_https_refuse_avant_tout_acces(tmp_path, monkeypatch):
    monkeypatch.setattr(updates.urllib.request, "urlopen",
                        lambda *a, **k: pytest.fail("aucun accès réseau attendu"))
    with pytest.raises(updates.DownloadError, match="HTTPS"):
        updates.download_asset(_asset(b"x", url="http://exemple.test/BDA.zip"), tmp_path)
