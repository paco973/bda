"""
Contexte TLS partagé (`logos/tls.py`) : les deux modules réseau doivent
vérifier les certificats avec un magasin qui reste garni même quand celui du
système est absent — cas de l'appli gelée sur le poste de l'opérateur.
"""
import ssl

import certifi
import pytest

from logos import tls, updates
from logos.data import scrape


def test_contexte_verifiant_et_garni(monkeypatch):
    # Système sans aucune autorité : certifi doit suffire à lui seul. On ne
    # vide pas le magasin via SSL_CERT_FILE : sous Windows, Python lit les
    # autorités du magasin système et ignore ces variables — on remplace donc
    # le contexte de départ par un contexte vérifiant mais vide.
    def empty_default_context():
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.verify_mode = ssl.CERT_REQUIRED
        context.check_hostname = True
        return context

    assert empty_default_context().cert_store_stats()["x509_ca"] == 0
    monkeypatch.setattr(tls.ssl, "create_default_context", empty_default_context)

    context = tls.ssl_context()
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True
    assert context.cert_store_stats()["x509_ca"] > 100


def test_certifi_ajoute_meme_si_le_systeme_a_des_autorites():
    # Magasin système présent mais incomplet : on complète, on ne remplace pas.
    system = ssl.create_default_context().cert_store_stats()["x509_ca"]
    if system == 0:
        pytest.skip("aucune autorité système sur cette machine")
    merged = tls.ssl_context().cert_store_stats()["x509_ca"]
    assert merged >= system


def test_sans_certifi_ne_leve_pas(monkeypatch):
    monkeypatch.setattr(certifi, "where", lambda: "/nonexistent/cacert.pem")
    context = tls.ssl_context()  # OSError avalée
    assert context.verify_mode == ssl.CERT_REQUIRED


def test_les_deux_modules_reseau_passent_le_contexte(monkeypatch):
    seen = []

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self, *args):
            return b"{}"

    def fake_urlopen(url, timeout=None, context=None):
        seen.append(context)
        return _Resp()

    monkeypatch.setattr(scrape.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(updates.urllib.request, "urlopen", fake_urlopen)
    scrape.fetch(scrape.INDEX_URL)
    updates.check_for_update("https://example.invalid/latest.json")
    assert len(seen) == 2
    assert all(isinstance(ctx, ssl.SSLContext) for ctx in seen)
