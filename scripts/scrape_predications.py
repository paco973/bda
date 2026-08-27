#!/usr/bin/env python3
"""
Import des prédications depuis branham.fr vers l'asset hors ligne de l'application.

La logique de récupération vit dans `logos/data/scrape.py`, partagée avec le
téléchargement intégré à l'application (« Télécharger les prédications… ») —
ce script n'est que l'habillage en ligne de commande, pratique pour générer
l'asset du dépôt ou un corpus à déposer sur un poste.

    python scripts/scrape_predications.py --letters A            # lettre A
    python scripts/scrape_predications.py                        # tout l'index
    python scripts/scrape_predications.py --letters A --limit 5  # test rapide
    python scripts/scrape_predications.py --dry-run              # compte sans télécharger

⚠️ Le contenu des prédications est sous copyright (branham.fr / VGR). N'utilisez
cet import que si vous disposez des droits nécessaires pour votre usage.
"""
import argparse
import gzip
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from logos.data import scrape
# Ré-exports : les tests (et d'éventuels usages interactifs) chargent les
# parseurs via ce module depuis toujours.
from logos.data.scrape import INDEX_URL, fetch, parse_index, parse_paragraphs  # noqa: F401

# Sortie console en UTF-8 (titres accentués) quel que soit l'environnement.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

DEFAULT_OUT = Path(__file__).resolve().parent.parent / "logos" / "assets" / "predications.json.gz"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Import des prédications branham.fr")
    parser.add_argument("--letters", default="",
                        help="Lettres initiales à importer (ex. « A » ou « ABC » ; "
                             "vide = tout l'index).")
    parser.add_argument("--limit", type=int, default=0,
                        help="Nombre maximum de prédications (0 = pas de limite).")
    parser.add_argument("--delay", type=float, default=1.0,
                        help="Pause (s) entre deux requêtes (politesse serveur).")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT,
                        help="Fichier de sortie (.json.gz).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Ne rien télécharger : afficher seulement le décompte.")
    args = parser.parse_args(argv)

    print(f"Récupération de l'index {scrape.INDEX_URL} …")
    if args.dry_run:
        entries = scrape.select_entries(
            scrape.parse_index(scrape.fetch(scrape.INDEX_URL)), args.letters, args.limit
        )
        print(f"  {len(entries)} prédications sélectionnées (dry-run : rien téléchargé).")
        return

    def on_progress(i, total, label):
        print(f"[{i}/{total}] {label}", flush=True)

    data = scrape.download_corpus(
        letters=args.letters, limit=args.limit, delay=args.delay,
        on_progress=on_progress,
    )
    total_paragraphs = sum(len(p["paragraphs"]) for p in data["predications"])
    print(f"\nTotal : {len(data['predications'])} prédications, "
          f"{total_paragraphs} paragraphes.")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(args.out, "wt", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"Écrit : {args.out}")


if __name__ == "__main__":
    main()
