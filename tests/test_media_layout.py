import pytest


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
    """C'est Streamlit lui-même qui valide son contrat — on ne le réimplémente pas."""
    at = rendre_app(_app, dimensions=(largeur, hauteur))
    assert not at.exception


@pytest.mark.parametrize(
    "largeur, hauteur, attendu",
    [
        (640, 360, [0.1, 0.8, 0.1]),
        (720, 1280, [2 / 7, 3 / 7, 2 / 7]),
    ],
)
def test_les_poids_rendus_reproduisent_le_calage(
    largeur, hauteur, attendu, rendre_app, poids_apercu
):
    """Preuve que les floats reproduisent [1,8,1] / [2,3,2] : Streamlit normalise
    Les poids sont définits à dire d'experts"""
    at = rendre_app(_app, dimensions=(largeur, hauteur))

    assert not at.exception
    assert poids_apercu(at) == pytest.approx(attendu)


def test_le_contenu_est_dans_la_colonne_centrale(rendre_app):
    at = rendre_app(_app, dimensions=(640, 360))

    gauche, milieu, droite = at.get("column")
    assert len(gauche.children) == 0
    assert len(milieu.children) == 1
    assert len(droite.children) == 0


@pytest.mark.parametrize(
    "dimensions, dimension_fautive",
    [
        ((0, 100), "largeur"),
        ((100, 0), "hauteur"),
    ],
)
def test_dimensions_invalides_font_remonter_la_valueerror(
    dimensions, dimension_fautive, rendre_app
):
    """Politique assumée : pas de repli silencieux, l'erreur remonte.

    Le message doit désigner l'argument fautif (largeur ou hauteur), pas juste
    « invalide » — même contrat que test_layout.py.
    """
    at = rendre_app(_app, dimensions=dimensions)

    assert at.exception
    # .proto.type porte la classe de l'exception ; .type vaudrait "exception"
    # (le type d'ÉLÉMENT Streamlit), ce qui ne prouverait rien.
    assert at.exception[0].proto.type == "ValueError"
    assert dimension_fautive in at.exception[0].value
