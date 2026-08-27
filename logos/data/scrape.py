"""
Récupération du corpus de prédications depuis branham.fr.

Logique partagée entre le script `scripts/scrape_predications.py` et le
téléchargement intégré à l'application (« Télécharger les prédications… »).
Avec `logos/updates.py`, c'est l'un des deux seuls modules qui accèdent au
réseau — et uniquement sur action explicite de l'opérateur : rien n'est
téléchargé automatiquement.

⚠️ Le contenu des prédications est sous copyright (branham.fr / VGR) : usage
interne uniquement, jamais de redistribution publique. L'interface impose une
confirmation rappelant ces conditions avant tout téléchargement.

Note technique : la structure de l'index (tableau : code date · titre FR ·
titre EN · lien) est stable. L'extraction des paragraphes repose sur le
conteneur `scalText` et la numérotation séquentielle (1, 2, 3, …) du corps du
sermon ; si le site change son balisage, c'est ici qu'il faudra ajuster.

Aucune dépendance Qt : testable tel quel (réseau simulé dans les tests).
"""
import html as html_module
import re
import time
import unicodedata
import urllib.request
from urllib.parse import quote

BASE = "https://branham.fr"
INDEX_URL = f"{BASE}/sermons"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
SOURCE = "branham.fr"


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


def title_initial(title: str) -> str:
    """Initiale de classement, désaccentuée comme dans l'application
    (« Élie » -> E, « Être » -> E) : un filtre A…Z couvre tous les titres."""
    for ch in title:
        if ch.isalpha():
            return unicodedata.normalize("NFD", ch)[0].upper()
    return "#"


def select_entries(entries, letters=None, limit=0):
    """Filtre l'index par initiales (None/"" = tout) et dédoublonne par URL en
    conservant l'ordre ; `limit` borne le résultat (0 = pas de limite)."""
    if letters:
        wanted = {c.upper() for c in letters if c.isalpha()}
        entries = [e for e in entries if title_initial(e["title_fr"]) in wanted]
    seen, unique = set(), []
    for entry in entries:
        if entry["url"] not in seen:
            seen.add(entry["url"])
            unique.append(entry)
    if limit:
        unique = unique[:limit]
    return unique


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
#  Téléchargement complet
# --------------------------------------------------------------------------- #
def _polite_sleep(delay, should_stop):
    """Pause de politesse, par petits pas pour rester réactif à l'annulation."""
    slept = 0.0
    while slept < delay:
        if should_stop is not None and should_stop():
            return
        step = min(0.2, delay - slept)
        time.sleep(step)
        slept += step


def download_corpus(letters=None, limit=0, delay=1.0,
                    on_progress=None, should_stop=None):
    """Télécharge l'index puis chaque prédication, avec une pause de politesse
    entre deux requêtes.

    `on_progress(i, total, libellé)` est appelé avant chaque prédication ;
    `should_stop()` (interrogé en continu) permet d'annuler : la fonction
    retourne alors None et rien ne doit être conservé. Une prédication dont la
    page échoue (réseau, décodage) est simplement sautée. Toute erreur sur
    l'index lui-même (site injoignable) remonte à l'appelant.

    Retourne le corpus {"source": …, "predications": [...]}."""
    entries = select_entries(parse_index(fetch(INDEX_URL)), letters, limit)
    total = len(entries)
    predications = []
    for i, entry in enumerate(entries, 1):
        if should_stop is not None and should_stop():
            return None
        if on_progress is not None:
            on_progress(i, total, f"{entry['date_code']}  {entry['title_fr']}")
        try:
            paragraphs = parse_paragraphs(fetch(entry["url"]))
        except Exception:  # réseau, décodage… : on saute cette prédication
            continue
        predications.append({
            "date_code": entry["date_code"],
            "title_fr": entry["title_fr"],
            "title_en": entry["title_en"],
            "paragraphs": paragraphs,
        })
        if delay:
            _polite_sleep(delay, should_stop)
    if should_stop is not None and should_stop():
        return None
    return {"source": SOURCE, "predications": predications}
