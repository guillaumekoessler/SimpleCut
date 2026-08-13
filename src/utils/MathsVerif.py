"""Module ayant pour objectif de centraliser les fonctions mathématiques utiles pour l'ensemble du projet"""

from __future__ import annotations

import math


def _valider_positive_finite(nom: str, valeur: float, test_positive=True) -> None:
    """Vérifie qu'un nombre est un nombre fini strictement positif.

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
    if valeur <= 0 and test_positive == True:
        raise ValueError(f"{nom} doit être > 0, reçu : {valeur!r}")
