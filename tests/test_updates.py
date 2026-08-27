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
