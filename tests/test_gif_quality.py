"""Cadences GIF : trois vitesses nommées, aucune ne dérive."""

import pytest

from tests.donnees import FPS_SOURCES, VITESSES_PAR_SOURCE
from utils.GifQuality import FPS_EXACTS, vitesse_par_defaut, vitesses_disponibles


@pytest.mark.parametrize("fps_source", FPS_SOURCES)
def test_aucune_vitesse_proposee_ne_derive(fps_source):
    """L'invariant qualité, et la raison d'être du module.

    Un GIF stocke le délai inter-image en CENTIÈMES de seconde et Pillow tronque
    1000/fps à la dizaine de ms inférieure. Mesuré : fps=15 → 60 ms → 16,67 i/s,
    soit +11 % de vitesse. Aucune valeur proposée à l'utilisateur ne doit
    pouvoir tomber dans ce piège.
    """
    proposees = vitesses_disponibles(fps_source)

    assert proposees, "il doit toujours rester au moins une vitesse jouable"
    for nom, fps in proposees.items():
        assert (
            100 % fps == 0
        ), f"{nom} ({fps} i/s) : 1000/{fps} n'est pas un multiple de 10 ms"
        assert fps in FPS_EXACTS


@pytest.mark.parametrize("fps_source, attendues, defaut", VITESSES_PAR_SOURCE)
def test_les_vitesses_et_le_defaut_suivent_le_fps_source(fps_source, attendues, defaut):
    """Le catalogue est PLAFONNÉ par la source : on ne propose jamais de
    fabriquer des images que la vidéo n'a pas.

    Seule exception, assumée : sous 1 i/s la source ne peut plus rien plafonner
    du tout, et ConversionParams exige fps >= 1 — on rend 1.
    """
    proposees = vitesses_disponibles(fps_source)

    assert proposees == attendues
    assert vitesse_par_defaut(proposees) == defaut
    assert defaut in proposees
