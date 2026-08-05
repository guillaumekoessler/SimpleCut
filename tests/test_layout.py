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


def test_continuite_aux_jonctions():
    """Pas de saut visuel quand un média change de régime.

    Ce test ne vérifie pas une valeur mais un RACCORD : il interdit de régler
    FRACTION_MIN / FRACTION_MAX sans réaliser qu'on créerait une discontinuité.
    """
    assert fraction_media(RATIO_PLANCHER, 1) == pytest.approx(FRACTION_MIN)
    assert fraction_media(RATIO_PLAFOND, 1) == pytest.approx(FRACTION_MAX)

    epsilon = 1e-6
    assert fraction_media(RATIO_PLANCHER - epsilon, 1) == pytest.approx(
        fraction_media(RATIO_PLANCHER + epsilon, 1), abs=1e-5
    )
    assert fraction_media(RATIO_PLAFOND - epsilon, 1) == pytest.approx(
        fraction_media(RATIO_PLAFOND + epsilon, 1), abs=1e-5
    )


def test_monotonie():
    """Plus large ⇒ jamais plus petit."""
    ratios = [0.1, 0.5, 0.5625, RATIO_PLANCHER, 1.0, 4 / 3, 1.5, RATIO_PLAFOND, 2.4, 10]
    fractions = [fraction_media(r, 1) for r in ratios]
    assert fractions == sorted(fractions)


def test_contrat_streamlit(largeur, hauteur):
    """Le contrat de st.columns : poids de somme 1, tous strictement positifs.

    Streamlit lève StreamlitInvalidColumnSpecError si un poids est <= 0.
    """
    poids = poids_colonnes_media(largeur, hauteur)
    assert len(poids) == 3
    assert sum(poids) == pytest.approx(1)
    assert all(p > 0 for p in poids)


def test_contrat_des_constantes():
    """Un futur réglage du calage ne peut pas casser la mise en page."""
    # < 1 strict : garantit un poids latéral (1 - f) / 2 > 0.
    assert 0 < FRACTION_MIN <= FRACTION_MAX < 1
    # À f = 1/3 les trois colonnes sont égales : le média n'est plus « au centre ».
    assert FRACTION_MIN > 1 / 3
    # Sinon le régime médian est vide ou inversé.
    assert RATIO_PLANCHER < RATIO_PLAFOND


@pytest.mark.parametrize(
    "largeur, hauteur",
    [
        (0, 100),
        (100, 0),
        (0, 0),
        (-1, 10),
        (10, -1),
        (-1, -1),
        (float("nan"), 10),
        (10, float("nan")),
        (float("inf"), 10),
        (10, float("inf")),
    ],
)
def test_dimensions_invalides(largeur, hauteur):
    """Chaque argument est validé séparément, avant toute division."""
    with pytest.raises(ValueError):
        fraction_media(largeur, hauteur)

    with pytest.raises(ValueError):
        poids_colonnes_media(largeur, hauteur)


def test_message_erreur_nomme_la_dimension_fautive():
    """Le message doit désigner l'argument en cause, pas juste « invalide »."""
    with pytest.raises(ValueError, match="hauteur"):
        fraction_media(100, 0)
    with pytest.raises(ValueError, match="largeur"):
        fraction_media(-5, 100)
