#!/usr/bin/env python3
"""
Import des prédications depuis branham.fr vers l'asset hors ligne de l'application.

Ce script récupère un sous-ensemble (par défaut : les prédications dont le titre
français commence par « A ») et génère
`logos/assets/predications.json.gz`, importé au premier lancement de l'appli.

Il n'utilise que la bibliothèque standard (aucune dépendance à installer).

    python scripts/scrape_predications.py --letters A            # lettre A
    python scripts/scrape_predications.py --letters ABC          # A, B, C
    python scripts/scrape_predications.py --letters A --limit 5  # test rapide
    python scripts/scrape_predications.py --letters A --dry-run  # compte sans écrire

⚠️ Le contenu des prédications est sous copyright (branham.fr / VGR). N'utilisez
cet import que si vous disposez des droits nécessaires pour votre usage.

Note technique : la structure de l'index (tableau : code date · titre FR · titre
EN · lien) est stable. L'extraction des paragraphes repose sur la numérotation
séquentielle (1, 2, 3, …) du corps du sermon ; si le site change son balisage,
c'est la fonction `parse_paragraphs()` qu'il faudra ajuster. Utilisez `--limit`
puis vérifiez le nombre de paragraphes annoncé avant un import complet.
"""
import argparse
import gzip
import html as html_module
import json
import re
import sys
import time
import urllib.request
from urllib.parse import quote
from pathlib import Path

# Sortie console en UTF-8 (titres accentués) quel que soit l'environnement.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

BASE = "https://branham.fr"
INDEX_URL = f"{BASE}/sermons"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
DEFAULT_OUT = Path(__file__).resolve().parent.parent / "logos" / "assets" / "predications.json.gz"


def fetch(url: str) -> str:
    url = quote(url, safe=":/?&=#%")  # échappe tout caractère non-ASCII de l'URL
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", "ignore")


# --------------------------------------------------------------------------- #
#  Index : lignes « code date · titre FR (lien) · titre EN »
# --------------------------------------------------------------------------- #
_ROW = re.compile(
    r'<span class="arial text-nowrap">(?P<date>[^<]+)</span>.*?'
    r'<a href="(?P<url>/sermons/\d+-[^"]+)"[^>]*>(?P<fr>.*?)</a>.*?'
    r'<td class="d-none d-xl-table-cell">(?P<en>.*?)</td>',
    re.DOTALL,
)


def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    return html_module.unescape(text).strip()


def parse_index(index_html: str):
    """Retourne la liste des prédications de l'index (métadonnées + URL)."""
    entries = []
    for m in _ROW.finditer(index_html):
        entries.append({
            "date_code": _clean(m.group("date")),
            "title_fr": _clean(m.group("fr")),
            "title_en": _clean(m.group("en")),
            "url": BASE + m.group("url"),
        })
    return entries


# --------------------------------------------------------------------------- #
#  Corps d'un sermon : paragraphes numérotés séquentiellement
# --------------------------------------------------------------------------- #
# Le texte du sermon (et lui seul) vit dans <div class="scalText …"> : cibler ce
# conteneur exclut l'habillage de la page (durée « 1 heure … », liens PDF,
# sélecteur de langue, menu de pied de page) qui polluait les paragraphes.
_SCALTEXT = re.compile(r'<div class="scalText[^"]*"[^>]*>', re.I)


def _body_text(sermon_html: str) -> str:
    """Texte visible du corps du sermon (scripts/styles/balises retirés)."""
    m = _SCALTEXT.search(sermon_html)
    if m:
        end = sermon_html.find("</div>", m.end())
        region = sermon_html[m.end():end] if end >= 0 else sermon_html[m.end():]
    else:
        # Repli (ancien comportement) si le site change son balisage.
        start = sermon_html.find('class="content"')
        region = sermon_html[start:] if start >= 0 else sermon_html
    region = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", region, flags=re.DOTALL | re.I)
    region = re.sub(r"<br\s*/?>", "\n", region, flags=re.I)
    region = re.sub(r"<p[^>]*>|</p>|</div>|</td>|</tr>", "\n", region, flags=re.I)
    region = re.sub(r"<[^>]+>", " ", region)
    return html_module.unescape(region)


def parse_paragraphs(sermon_html: str):
    """Découpe le corps en paragraphes d'après leur numéro (1, 2, 3, …).

    On repère les entiers apparaissant dans l'ordre attendu (1 puis 2 puis 3…) ;
    le texte entre deux numéros consécutifs forme un paragraphe. Robuste aux
    nombres présents dans le texte : un marqueur doit être en début de ligne
    (les <p>/<br> du site y placent chaque numéro), suivi d'une espace, et être
    le prochain numéro attendu.
    """
    text = _body_text(sermon_html)
    numbers = list(re.finditer(r"(?m)^[ \t]*(\d{1,4})(?=\s)", text))
    points, expected = [], 1
    for m in numbers:
        if int(m.group(1)) == expected:
            points.append(m)
            expected += 1
    paragraphs = []
    for i, m in enumerate(points):
        chunk_end = points[i + 1].start() if i + 1 < len(points) else len(text)
        para = re.sub(r"\s+", " ", text[m.end():chunk_end]).strip()
        if para:
            paragraphs.append(para)
    return paragraphs


# --------------------------------------------------------------------------- #
#  Programme principal
# --------------------------------------------------------------------------- #
def main(argv=None):
    parser = argparse.ArgumentParser(description="Import des prédications branham.fr")
    parser.add_argument("--letters", default="A",
                        help="Lettres initiales à importer (ex. « A » ou « ABC »).")
    parser.add_argument("--limit", type=int, default=0,
                        help="Nombre maximum de prédications (0 = pas de limite).")
    parser.add_argument("--delay", type=float, default=1.0,
                        help="Pause (s) entre deux requêtes (politesse serveur).")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT,
                        help="Fichier de sortie (.json.gz).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Ne rien écrire : afficher seulement le décompte.")
    args = parser.parse_args(argv)

    wanted = {c.upper() for c in args.letters if c.isalpha()}
    print(f"Récupération de l'index {INDEX_URL} …")
    entries = parse_index(fetch(INDEX_URL))
    print(f"  {len(entries)} prédications listées.")

    def initial(title):
        for ch in title:
            if ch.isalpha():
                return ch.upper()
        return "#"

    selected = [e for e in entries if initial(e["title_fr"]) in wanted]
    # Dédoublonne par URL en conservant l'ordre.
    seen, unique = set(), []
    for e in selected:
        if e["url"] not in seen:
            seen.add(e["url"])
            unique.append(e)
    selected = unique
    if args.limit:
        selected = selected[:args.limit]
    print(f"  {len(selected)} prédications pour {sorted(wanted)}.")

    predications = []
    for i, entry in enumerate(selected, 1):
        print(f"[{i}/{len(selected)}] {entry['date_code']}  {entry['title_fr']}", flush=True)
        try:
            paragraphs = parse_paragraphs(fetch(entry["url"]))
        except Exception as exc:  # réseau, décodage… : on saute cette prédication
            print(f"    ⚠ échec ({exc}) — ignorée", file=sys.stderr)
            continue
        print(f"    {len(paragraphs)} paragraphes")
        predications.append({
            "date_code": entry["date_code"],
            "title_fr": entry["title_fr"],
            "title_en": entry["title_en"],
            "paragraphs": paragraphs,
        })
        if args.delay:
            time.sleep(args.delay)

    print(f"\nTotal : {len(predications)} prédications, "
          f"{sum(len(p['paragraphs']) for p in predications)} paragraphes.")
    if args.dry_run:
        print("(dry-run : rien n'a été écrit)")
        return

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(args.out, "wt", encoding="utf-8") as f:
        json.dump({"source": "branham.fr", "predications": predications}, f, ensure_ascii=False)
    print(f"Écrit : {args.out}")


if __name__ == "__main__":
    main()
