import pytest

from tests.donnees import CALAGES_REFERENCE, DIMENSIONS_INVALIDES


def _app():
    # Import DANS le corps : obligatoire pour AppTest.from_function.
    import streamlit as st

    from components.MediaLayout import colonne_media

    largeur, hauteur = st.session_state["dimensions"]
    with colonne_media(largeur=largeur, hauteur=hauteur):
        st.text("média")


@pytest.mark.parametrize(
    "largeur, hauteur",
    [
        (640, 360),  # calage paysage
        (720, 1280),  # calage portrait
        (4, 3),  # flottant non trivial : 0.6000000000000001
        (1, 1),  # flottant non trivial : 0.45000000000000007
        (1, 10000),  # extrême portrait, ramené sur le plancher
        (10000, 1),  # extrême paysage, ramené sur le plafond
    ],
)
def test_aucune_erreur_poids(largeur, hauteur, rendre_app):
    """C'est Streamlit lui-même qui valide son contrat — on ne le réimplémente pas.

    L'absence d'exception est affirmée par rendre_app : rendre EST le test.
    """
    rendre_app(_app, dimensions=(largeur, hauteur))


@pytest.mark.parametrize("largeur, hauteur, poids", CALAGES_REFERENCE)
def test_les_poids_rendus_reproduisent_le_calage(
    largeur, hauteur, poids, rendre_app, poids_apercu
):
    """Preuve que les floats reproduisent [1,8,1] / [2,3,2] : Streamlit normalise
    Les poids sont définits à dire d'experts"""
    at = rendre_app(_app, dimensions=(largeur, hauteur))

    assert poids_apercu(at) == pytest.approx(poids)


def test_le_contenu_est_dans_la_colonne_centrale(rendre_app):
    at = rendre_app(_app, dimensions=(640, 360))

    gauche, milieu, droite = at.get("column")
    assert len(gauche.children) == 0
    assert len(milieu.children) == 1
    assert len(droite.children) == 0


@pytest.mark.parametrize("largeur, hauteur, fautive", DIMENSIONS_INVALIDES)
def test_dimensions_invalides_font_remonter_la_valueerror(
    largeur, hauteur, fautive, rendre_app
):
    """Politique assumée : pas de repli silencieux, l'erreur remonte.

    Le message doit désigner l'argument fautif (largeur ou hauteur), pas juste
    « invalide » — même contrat que test_layout.py.
    """
    at = rendre_app(_app, dimensions=(largeur, hauteur), sans_erreur=False)

    assert at.exception
    # .proto.type porte la classe de l'exception ; .type vaudrait "exception"
    # (le type d'ÉLÉMENT Streamlit), ce qui ne prouverait rien.
    assert at.exception[0].proto.type == "ValueError"
    assert fautive in at.exception[0].value
