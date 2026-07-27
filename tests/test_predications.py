"""Tests des prédications : couche données, parseurs du script d'import, panneau."""
import importlib.util
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from logos.data import database, predications

SAMPLE = {
    "predications": [
        {"date_code": "59-1004", "title_fr": "Abraham", "title_en": "Abraham",
         "paragraphs": ["Un.", "Deux.", "Trois."]},
        {"date_code": "61-0212", "title_fr": "Abraham et sa postérité",
         "title_en": "Abraham's Seed", "paragraphs": ["A.", "B."]},
        {"date_code": "62-1230", "title_fr": "Absolu, L'", "title_en": "The Absolute",
         "paragraphs": ["Seul."]},
        {"date_code": "63-0101", "title_fr": "Élie", "title_en": "Elijah",
         "paragraphs": ["E1.", "E2."]},
    ]
}


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "bda.db")
    database.init_db()


# --------------------------- Couche données ---------------------------- #
def test_import_et_derivation():
    assert not predications.is_available()
    predications.import_data(SAMPLE)
    assert predications.is_available()
    assert predications.total_count() == 4


def test_lettres_et_prefixes():
    predications.import_data(SAMPLE)
    counts = dict(predications.letters_with_counts())
    assert counts["A"] == 3           # Abraham, Abraham et…, Absolu
    assert counts["E"] == 1           # Élie (accent ignoré)
    assert counts["B"] == 0
    # Abraham, « Abraham et… » et « Absolu » partagent tous le préfixe « Ab ».
    prefixes = dict(predications.prefixes_with_counts("A"))
    assert prefixes["Ab"] == 3
    assert dict(predications.prefixes_with_counts("E")) == {"El": 1}


def test_reimport_si_asset_change(tmp_path, monkeypatch):
    """`ensure_imported` réimporte quand l'asset embarqué change (empreinte
    stockée dans `meta`), et ne réimporte pas sinon."""
    import gzip
    import json

    asset = tmp_path / "predications.json.gz"
    monkeypatch.setattr(predications, "PREDICATIONS_ASSET", asset)

    def write_asset(data):
        with gzip.open(asset, "wt", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    write_asset(SAMPLE)
    predications.ensure_imported()
    assert predications.total_count() == 4

    # Même asset : pas de réimport (les ids restent stables).
    first_ids = [r["id"] for r in predications.list_by_prefix("Ab")]
    predications.ensure_imported()
    assert [r["id"] for r in predications.list_by_prefix("Ab")] == first_ids

    # Asset modifié (ex. paragraphes nettoyés) : réimport automatique.
    updated = {"predications": [dict(SAMPLE["predications"][0], paragraphs=["Propre."])]}
    write_asset(updated)
    predications.ensure_imported()
    assert predications.total_count() == 1
    pid = predications.list_by_prefix("Ab")[0]["id"]
    assert [p["text"] for p in predications.get_paragraphs(pid)] == ["Propre."]


def test_liste_paragraphes_recherche():
    predications.import_data(SAMPLE)
    rows = predications.list_by_prefix("Ab")
    assert [r["title_fr"] for r in rows] == ["Abraham", "Abraham et sa postérité", "Absolu, L'"]
    pid = rows[0]["id"]
    assert predications.paragraph_count(pid) == 3
    assert [p["text"] for p in predications.get_paragraphs(pid)] == ["Un.", "Deux.", "Trois."]
    found = predications.search("postérité")
    assert [r["title_fr"] for r in found] == ["Abraham et sa postérité"]


# ---------------------- Parseurs du script d'import -------------------- #
def _load_scraper():
    path = Path(__file__).resolve().parent.parent / "scripts" / "scrape_predications.py"
    spec = importlib.util.spec_from_file_location("scrape_predications", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_parse_index():
    scraper = _load_scraper()
    html = (
        '<tr><td><span class="arial text-nowrap">47-0412</span></td>'
        '<td><a href="/sermons/70-Faith" class="arialN text-dark">La Foi</a></td>'
        '<td class="d-none d-xl-table-cell">Faith</td></tr>'
        '<tr><td><span class="arial text-nowrap">59-1004</span></td>'
        '<td><a href="/sermons/1-Abraham" class="arialN">Abraham</a></td>'
        '<td class="d-none d-xl-table-cell">Abraham</td></tr>'
    )
    entries = scraper.parse_index(html)
    assert len(entries) == 2
    assert entries[0]["date_code"] == "47-0412"
    assert entries[0]["title_fr"] == "La Foi"
    assert entries[0]["title_en"] == "Faith"
    assert entries[0]["url"].endswith("/sermons/70-Faith")


def test_parse_paragraphs_par_numerotation():
    scraper = _load_scraper()
    html = (
        '<div class="content"><p>1 Premier paragraphe.</p>'
        '<p>2 Deuxième paragraphe avec le nombre 40 au milieu.</p>'
        '<p>3 Troisième.</p></div>'
    )
    paras = scraper.parse_paragraphs(html)
    assert len(paras) == 3
    assert paras[0] == "Premier paragraphe."
    assert paras[1].startswith("Deuxième")
    assert paras[2] == "Troisième."


def test_parse_paragraphs_ignore_habillage_page():
    """L'en-tête (durée « 1 heure … », liens) et le pied de page ne doivent
    jamais se retrouver dans les paragraphes : seul le conteneur scalText
    (balisage réel de branham.fr) contient le texte du sermon."""
    scraper = _load_scraper()
    html = (
        '<div class="content">'
        'La durée est de: 1 heure 37 minutes | La traduction: MS '
        '<a href="#">Télécharger le PDF</a> '
        '<a href="#">Voir le texte anglais seulement</a>'
        '<div class="scalText text-justify col-12 mt-2 p-0">'
        '<p>1 &nbsp;&nbsp; &nbsp;Merci, frère Neville. Bonjour les amis.<br>\n'
        '<br>\n'
        '2 &nbsp;&nbsp; &nbsp;J’ai dû prendre le train de onze heures.<br>\n'
        '</p></div>'
        '<a href="/">Accueil</a> <a href="/bio">Biographie</a></div>'
    )
    paras = scraper.parse_paragraphs(html)
    assert paras == [
        "Merci, frère Neville. Bonjour les amis.",
        "J’ai dû prendre le train de onze heures.",
    ]


# ------------------------------ Panneau UI ---------------------------- #
@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_panneau_predication(qapp):
    predications.import_data(SAMPLE)
    from logos.ui.predication_panel import PredicationPanel

    panel = PredicationPanel()
    # Démarre sur la 1re lettre disponible (A), 1er préfixe (Ab), 1re prédication.
    assert panel._letter == "A"
    assert panel._prefix == "Ab"
    assert panel._predication["title_fr"] == "Abraham"
    deck, index = panel.current_deck()
    assert len(deck) == 3 and index == 0
    assert deck[0].endswith("Abraham · §1")

    # Navigation par diapositive (paragraphe)
    panel.select_slide(2)
    assert panel._paragraph == 3


def test_panneau_indisponible(qapp):
    from logos.ui.predication_panel import PredicationPanel

    panel = PredicationPanel()  # base vide : rien importé
    assert not panel.project_btn.isEnabled()
    assert panel.current_deck() == ([], 0)
