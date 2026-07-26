from utils.Dimensions import (
    LARGEUR_APERCU_GIF,
    LARGEUR_APERCU_VIDEO,
    LARGEUR_VIGNETTE_ACCUEIL,
    LARGEUR_VIGNETTE_SIDEBAR,
)


def test_dimensions_sont_des_entiers_plausibles():
    for valeur in (
        LARGEUR_APERCU_GIF,
        LARGEUR_APERCU_VIDEO,
        LARGEUR_VIGNETTE_ACCUEIL,
        LARGEUR_VIGNETTE_SIDEBAR,
    ):
        assert isinstance(valeur, int)
        assert 16 <= valeur <= 2000
