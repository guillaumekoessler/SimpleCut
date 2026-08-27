"""Cadences GIF : trois vitesses nommées, aucune ne dérive.

Contrainte physique du format : un GIF stocke le délai d'affichage de chaque
image en CENTIÈMES de seconde. Pillow — l'encodeur qu'appelle utils.GifExport —
tronque `1000/fps` à la dizaine de millisecondes inférieure. Une cadence dont
`100/fps` n'est pas entier produit donc un GIF qui ne joue PAS à la vitesse
demandée. Mesuré sur MoviePy 2.2.1, délais relus dans le fichier produit :

    fps=15 → 66,7 ms tronqué à 60 ms → 16,67 i/s  (+11 %)
    fps=30 → 33,3 ms tronqué à 30 ms → 33,33 i/s  (+11 %)
    fps=12 → 83,3 ms tronqué à 80 ms → 12,50 i/s  (+4 %)
    fps=10 → 100 ms                  → 10,00 i/s  (exact)

Couche pure : zéro import Streamlit, zéro import MoviePy — même contrat que
utils.Layout et utils.PreviewGif.
"""

from __future__ import annotations

from utils.MathsVerif import _valider_positive_finite

# Les seules cadences entières fidèles : celles dont 100/fps est entier, donc
# les diviseurs de 100. Toute valeur proposée à l'utilisateur sort d'ici.
# Arrêté à 25 volontairement : 50 et 100 divisent bien 100, mais leurs délais
# (20 et 10 ms) tombent sous le seuil que les navigateurs ramènent d'office à
# 100 ms. Exacts sur le papier, faux à l'écran — ils n'ont rien à faire ici.
FPS_EXACTS: tuple[int, ...] = (1, 2, 4, 5, 10, 20, 25)

# Le catalogue offert à l'utilisateur, du plus lent au plus rapide. Trois
# cadences d'usage courant sur le web, échelonnées en doublement, toutes dans
# FPS_EXACTS. On expose des NOMS plutôt que des nombres : « 12 ou 15 ? » n'a
# pas de bonne réponse pour qui fabrique un GIF, « fluide ou léger ? » si.
VITESSES: tuple[tuple[str, int], ...] = (("Lent", 5), ("Moyen", 10), ("Rapide", 20))

# Présélection quand la source la permet : 10 i/s est la cadence GIF canonique.
VITESSE_PAR_DEFAUT = "Moyen"


def vitesses_disponibles(fps_source: float) -> dict[str, int]:
    """Vitesses proposables pour une vidéo de cette cadence.

    Le catalogue est PLAFONNÉ par la source : à 10 i/s, « Rapide » (20 i/s)
    n'apporterait que des images dupliquées, du poids de fichier et aucune
    fluidité. Mieux vaut ne pas l'offrir que de le laisser décevoir.

    Args:
        fps_source: Cadence de la vidéo source en images/s (> 0, finie).

    Returns:
        Dictionnaire ORDONNÉ du plus lent au plus rapide, jamais vide, dont
        toutes les valeurs sont dans FPS_EXACTS.

    Raises:
        ValueError: Si fps_source est <= 0 ou non finie.
                    Un argument non numérique lève TypeError (non attrapé).
    """
    _valider_positive_finite("fps_source", fps_source)

    disponibles = {nom: fps for nom, fps in VITESSES if fps <= fps_source}
    if disponibles:
        return disponibles

    # Source plus lente que « Lent » : le catalogue ne s'applique plus. On rend
    # la cadence exacte la plus haute encore atteignable, sous le nom le plus
    # lent — et jamais moins de 1 i/s, pour qu'une source pathologique (moins
    # d'une image par seconde) produise quand même un GIF.
    repli = max((fps for fps in FPS_EXACTS if fps <= fps_source), default=FPS_EXACTS[0])
    return {VITESSES[0][0]: repli}


def vitesse_par_defaut(vitesses: dict[str, int]) -> str:
    """Nom de la vitesse à présélectionner parmi celles disponibles.

    Args:
        vitesses: Ce que rend vitesses_disponibles (ordonné, non vide).

    Returns:
        VITESSE_PAR_DEFAUT s'il est offert, sinon la plus rapide disponible.

    Raises:
        ValueError: Si vitesses est vide.
    """
    if not vitesses:
        raise ValueError("vitesses ne doit pas être vide")

    if VITESSE_PAR_DEFAUT in vitesses:
        return VITESSE_PAR_DEFAUT

    # Le dictionnaire est ordonné du plus lent au plus rapide : à défaut de
    # « Moyen », on présélectionne la plus rapide encore offerte.
    return next(reversed(vitesses))
