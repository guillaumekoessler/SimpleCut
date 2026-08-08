"""Proportions d'affichage des médias : largeur de colonne selon le ratio.

Modèle « hauteur plafonnée + largeur plancher » :
    f(r) = clamp(HAUTEUR_CIBLE * r, FRACTION_MIN, FRACTION_MAX)
Seul le RATIO du média compte, jamais sa taille absolue.
"""

from __future__ import annotations

import math

from utils.Dimensions import (
    FRACTION_MAX,
    FRACTION_MIN,
    HAUTEUR_CIBLE,
    RATIO_PLAFOND,
    RATIO_PLANCHER,
)


def _valider_dimension(nom: str, valeur: float) -> None:
    """Vérifie qu'une dimension est un nombre fini strictement positif.

    Args:
        nom: Nom de la dimension, utilisé dans le message d'erreur.
        valeur: Valeur à contrôler.

    Raises:
        ValueError: Si la valeur est non finie (nan, inf) ou <= 0.
        TypeError: Si la valeur n'est pas numérique (levée par math.isfinite,
                   volontairement non attrapée).
    """
    if not math.isfinite(valeur):
        raise ValueError(f"{nom} doit être un nombre fini, reçu : {valeur!r}")
    if valeur <= 0:
        raise ValueError(f"{nom} doit être > 0, reçu : {valeur!r}")


def fraction_media(largeur: float, hauteur: float) -> float:
    """Fraction de la largeur du conteneur à donner au média.

    Args:
        largeur: Largeur du média en pixels (> 0, finie).
        hauteur: Hauteur du média en pixels (> 0, finie).

    Returns:
        Un float dans [FRACTION_MIN, FRACTION_MAX].

    Raises:
        ValueError: Si l'une des dimensions est <= 0 ou non finie.
                    Un argument non numérique lève TypeError (non attrapé).
    """
    # On valide CHAQUE argument séparément — jamais le ratio : (-1, -1) donne
    # un ratio de 1.0 parfaitement valide. Et on valide AVANT de diviser, sinon
    # (100, 0) lèverait ZeroDivisionError au lieu du ValueError attendu.
    _valider_dimension("largeur", largeur)
    _valider_dimension("hauteur", hauteur)

    ratio = largeur / hauteur

    # Clamp idiomatique : max() applique le plancher, min() ensuite le plafond.
    return min(max(HAUTEUR_CIBLE * ratio, FRACTION_MIN), FRACTION_MAX)


def poids_colonnes_media(largeur: float, hauteur: float) -> tuple[float, float, float]:
    """Poids à passer à st.columns pour centrer un média de ce ratio.

    Args:
        largeur: Largeur du média en pixels (> 0, finie).
        hauteur: Hauteur du média en pixels (> 0, finie).

    Returns:
        (côté, milieu, côté), de somme 1, les trois strictement positifs
        — c'est le contrat exigé par st.columns.

    Raises:
        ValueError: Si l'une des dimensions est <= 0 ou non finie.
    """
    fraction = fraction_media(largeur, hauteur)
    # FRACTION_MAX < 1 garantit côté > 0, donc le contrat de st.columns.
    cote = (1 - fraction) / 2
    return (cote, fraction, cote)
