"""
Localisation des assets : priorité au fichier déposé par l'opérateur dans
`~/.bda/assets/`, repli sur celui livré avec l'application.
"""
import gzip
import json

import pytest

from logos import resources
from logos.data import database, predications


@pytest.fixture
def user_assets(tmp_path, monkeypatch):
    """Redirige le dossier utilisateur vers un dossier temporaire."""
    assets = tmp_path / "assets"
    assets.mkdir()
    monkeypatch.setattr(resources, "USER_ASSETS_DIR", assets)
    return assets


def test_asset_livre_par_defaut(user_assets):
    assert resources.asset_path("logo.png") == resources.bundled_asset_path("logo.png")


def test_depot_operateur_prioritaire(user_assets):
    (user_assets / "logo.png").write_bytes(b"nouveau logo")
    assert resources.asset_path("logo.png") == user_assets / "logo.png"


def test_dossier_ignore(user_assets):
    """Un dossier portant le nom d'un asset ne doit pas masquer le fichier livré."""
    (user_assets / "logo.png").mkdir()
    assert resources.asset_path("logo.png") == resources.bundled_asset_path("logo.png")


# --------------------------------------------------------------------------- #
#  Repli quand le fichier déposé est illisible
# --------------------------------------------------------------------------- #
def _write_corpus(path, titles):
    data = {"predications": [
        {"date_code": "62-0318", "title_fr": title, "title_en": "",
         "paragraphs": ["Bonjour."]}
        for title in titles
    ]}
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(data, f)


def test_corpus_depose_remplace_le_corpus_livre(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "bda.db")
    database.init_db()
    asset = tmp_path / "predications.json.gz"
    _write_corpus(asset, ["Une prédication déposée"])
    monkeypatch.setattr(predications, "PREDICATIONS_ASSET", asset)

    predications.ensure_imported()

    titres = [p["title_fr"] for p in predications.list_by_prefix("Un")]
    assert "Une prédication déposée" in titres


def test_corpus_depose_illisible_ne_bloque_pas_le_demarrage(tmp_path, monkeypatch, capsys):
    """Fichier corrompu déposé par l'opérateur : on prévient sur stderr et on
    repart du corpus livré, plutôt que d'empêcher l'application de s'ouvrir."""
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "bda.db")
    database.init_db()
    corrompu = tmp_path / "predications.json.gz"
    corrompu.write_bytes(b"ceci n'est pas du gzip")
    monkeypatch.setattr(predications, "PREDICATIONS_ASSET", corrompu)
    # Corpus « livré » simulé, pour ne pas dépendre de l'asset non versionné.
    livre = tmp_path / "livre.json.gz"
    _write_corpus(livre, ["Une prédication livrée"])
    monkeypatch.setattr(predications, "bundled_asset_path", lambda name: livre)

    predications.ensure_imported()  # ne doit pas lever

    assert "illisibles" in capsys.readouterr().err
    titres = [p["title_fr"] for p in predications.list_by_prefix("Un")]
    assert titres == ["Une prédication livrée"]  # le repli a bien été importé
