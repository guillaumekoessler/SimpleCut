"""Validations numériques partagées : finitude et positivité des grandeurs."""

from __future__ import annotations

import math


def _valider_fini(nom: str, valeur: float) -> None:
    """Vérifie qu'un nombre est fini, quel que soit son signe.

    À utiliser pour une grandeur que l'appelant borne lui-même : le signe est
    alors rattrapable, nan/inf non. Un nan traverserait min() et max() sans
    être clampé (toute comparaison avec nan étant fausse, min/max le laissent
    passer) et empoisonnerait la valeur en sortie.

    Args:
        nom: Nom de la grandeur, utilisé dans le message d'erreur.
        valeur: Valeur à contrôler.

    Raises:
        ValueError: Si la valeur est non finie (nan, inf, -inf).
        TypeError: Si la valeur n'est pas numérique (levée par math.isfinite,
            volontairement non attrapée).
    """
    if not math.isfinite(valeur):
        raise ValueError(f"{nom} doit être un nombre fini, reçu : {valeur!r}")


def _valider_positive_finite(
    nom: str, valeur: float, zero_autorise: bool = False
) -> None:
    """Vérifie qu'un nombre est fini et positif.

    Args:
        nom: Nom de la grandeur, utilisé dans le message d'erreur.
        valeur: Valeur à contrôler.
        zero_autorise: False (défaut) exige valeur > 0 ; True accepte
            valeur == 0 et ne rejette que le strictement négatif. Le domaine
            attendu change, donc le message d'erreur aussi.

    Raises:
        ValueError: Si la valeur est non finie (nan, inf), ou hors du domaine
            fixé par zero_autorise.
        TypeError: Si la valeur n'est pas numérique (levée par math.isfinite,
            volontairement non attrapée).
    """
    _valider_fini(nom, valeur)

    if zero_autorise:
        if valeur < 0:
            raise ValueError(f"{nom} doit être >= 0, reçu : {valeur!r}")
    elif valeur <= 0:
        raise ValueError(f"{nom} doit être > 0, reçu : {valeur!r}")
