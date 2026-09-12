"""
Contexte TLS commun aux deux seuls modules qui accèdent au réseau
(`logos/updates.py` et `logos/data/scrape.py`).

Pourquoi un module dédié : Python ne fait pas confiance au trousseau macOS ni
au magasin Windows. Il lit un fichier d'autorités de certification (`cert.pem`)
au chemin fixé quand *son* OpenSSL a été compilé. Sur le poste de l'opérateur,
ce chemin n'existe pas (appli gelée PyInstaller construite ailleurs, Python de
python.org dont « Install Certificates.command » n'a jamais été lancé…) et
chaque connexion HTTPS échoue en CERTIFICATE_VERIFY_FAILED — « branham.fr
injoignable », « serveur injoignable » — alors que le réseau va très bien.

Le paquet `certifi` (dépendance d'exécution, embarqué par `packaging/bda.spec`)
livre le magasin de Mozilla. On l'ajoute **toujours** au magasin du système,
et pas seulement quand celui-ci est vide : un magasin présent mais incomplet
ou périmé fait échouer la vérification exactement de la même façon.
`load_verify_locations` est additif, une autorité en double est sans effet.

Aucun accès réseau ici, aucun Qt : importable depuis `logos/data/`.
"""
import ssl


def ssl_context() -> ssl.SSLContext:
    """Contexte TLS vérifiant : autorités du système + celles de `certifi`.

    Ne lève jamais : sans `certifi` (ou fichier illisible), on rend le contexte
    du système tel quel — la connexion échouera peut-être, mais proprement,
    et l'appelant rapportera l'erreur comme n'importe quelle panne réseau."""
    context = ssl.create_default_context()
    try:
        import certifi

        context.load_verify_locations(cafile=certifi.where())
    except (ImportError, OSError, ssl.SSLError):
        pass
    return context
