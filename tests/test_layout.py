import math

import pytest

from utils.Layout import (
    FRACTION_MAX,
    FRACTION_MIN,
    HAUTEUR_CIBLE,
    RATIO_PLAFOND,
    RATIO_PLANCHER,
    fraction_media,
    poids_colonnes_media,
)


def test_calage_paysage_reproduit_1_8_1():
    """Calage utilisateur : 640x360 doit redonner exactement [1, 8, 1]"""
    assert fraction_media(640, 360) == pytest.approx(0.8)
    assert poids_colonnes_media(640, 360) == pytest.approx((0.1, 0.8, 0.1))


def test_calage_portrait_reproduit_2_3_2():
    """Calage utilisateur : 720x1280 doit redonner exactement [2, 3, 2]"""
    assert fraction_media(720, 1280) == pytest.approx(3 / 7)
    assert poids_colonnes_media(720, 1280) == pytest.approx((2 / 7, 3 / 7, 2 / 7))


def test_invariance_echelle():
    """Vérifie que les ratios sont correctement calculés par la fonction fraction media"""
    assert fraction_media(720, 1280) == fraction_media(1080, 1920)
    assert fraction_media(640, 360) == fraction_media(1920, 1080)


@pytest.mark.parametrize("ratio", [RATIO_PLANCHER, 1.0, 4 / 3, 1.5, RATIO_PLAFOND])
def test_regime_hauteur_constante(ratio):
    """On vérifie que la fraction donne toujours la hauteur cible

    hauteur_affichée = fraction / ratio, exprimée en fraction de la largeur
    du conteneur
    """
    hauteur_affichee = fraction_media(ratio, 1) / ratio
    assert hauteur_affichee == pytest.approx(HAUTEUR_CIBLE)


@pytest.mark.parametrize(
    "largeur, hauteur",
    [(21, 9), (2.39, 1), (1920, 800), (10000, 1)],
)
def test_plafond(largeur, hauteur):
    """Au-delà de 16:9, plus rien ne grandit."""
    assert fraction_media(largeur, hauteur) == pytest.approx(FRACTION_MAX)


@pytest.mark.parametrize(
    "largeur, hauteur",
    [(1, 3), (9, 21), (720, 1280), (1, 10000)],
)
def test_plancher(largeur, hauteur):
    """En deçà de RATIO_PLANCHER, plus rien ne rétrécit."""
    assert fraction_media(largeur, hauteur) == pytest.approx(FRACTION_MIN)
