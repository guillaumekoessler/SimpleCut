"""Proportions d'affichage des médias : largeur de colonne selon le ratio.

Modèle « hauteur plafonnée + largeur plancher » :
    f(r) = clamp(HAUTEUR_CIBLE * r, FRACTION_MIN, FRACTION_MAX)
Seul le RATIO du média compte, jamais sa taille absolue.
"""

from __future__ import annotations

from utils.Dimensions import FRACTION_MAX, FRACTION_MIN, HAUTEUR_CIBLE
from utils.MathsVerif import _valider_positive_finite


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
    _valider_positive_finite("largeur", largeur)
    _valider_positive_finite("hauteur", hauteur)

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
