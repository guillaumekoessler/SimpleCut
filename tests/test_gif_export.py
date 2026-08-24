"""Export GIF : cadence fidèle, comptes justes, échecs propres."""

from pathlib import Path

import pytest
from PIL import Image, ImageSequence

from tests.donnees import NOMS_A_ASSAINIR
from utils.GifClasses import ConversionParams
from utils.GifExport import convertir_en_gif, nom_fichier_gif


@pytest.fixture(scope="module")
def clip_anime(tmp_path_factory) -> Path:
    """Clip mp4 (64x48, 10 i/s, 1 s) dont CHAQUE image diffère.

    Indispensable ici, et c'est pourquoi on ne prend pas clip_reel : Pillow
    fusionne les images identiques consécutives d'un GIF et cumule leurs
    délais. Un clip de couleur unie produirait un GIF d'UNE image, sur lequel
    la cadence n'est plus lisible — exactement ce que ce fichier doit mesurer.
    """
    import numpy as np
    from moviepy import VideoClip

    def image(t: float):
        cadre = np.zeros((48, 64, 3), dtype="uint8")
        depart = int(60 * t)  # une barre blanche qui traverse le cadre
        cadre[:, depart : depart + 4] = 255
        return cadre

    chemin = tmp_path_factory.mktemp("anime") / "anime.mp4"
    VideoClip(image, duration=1.0).with_fps(10).write_videofile(
        str(chemin), logger=None
    )
    return chemin


def _delais_du_gif(chemin: Path) -> list[int]:
    """Délai d'affichage de chaque image du GIF, en millisecondes."""
    with Image.open(chemin) as gif:
        return [image.info["duration"] for image in ImageSequence.Iterator(gif)]


@pytest.mark.parametrize("fps", [5, 10])
def test_le_gif_joue_a_la_cadence_demandee(clip_anime, tmp_path, fps):
    """LA régression qualité : on relit les délais écrits dans le fichier.

    Seul test qui prouve que le GIF joue à la bonne vitesse. Avec l'ancien
    réglage par défaut (15 i/s) il échouerait : 1000/15 = 66,7 ms tronqué à
    60 ms, soit 16,67 i/s et une animation 11 % trop rapide.
    """
    params = ConversionParams(start_time=0.0, end_time=0.8, fps=fps)

    gif = convertir_en_gif(clip_anime, tmp_path / "sortie.gif", params)

    delais = _delais_du_gif(gif.chemin)
    assert len(delais) == gif.nb_images
    assert set(delais) == {1000 // fps}, "cadence dérivée : délai non multiple de 10 ms"
    assert sum(delais) == 1000 * gif.nb_images // fps


def test_un_segment_trop_court_est_refuse(clip_anime, tmp_path):
    """Atteignable en trois clics : 0,1 s de segment à la vitesse « Lent ».

    `int(0.1 × 5) == 0` : sans garde-fou, l'export « réussit » en ne produisant
    aucune image, dépose un fichier vide dans le cache, et la casse n'apparaît
    qu'à l'affichage, loin de sa cause.
    """
    sortie = tmp_path / "sortie.gif"

    with pytest.raises(ValueError, match="trop court"):
        convertir_en_gif(clip_anime, sortie, ConversionParams(0.0, 0.1, fps=5))

    assert not sortie.exists()


@pytest.mark.parametrize(
    "source_existe, fin, erreur",
    [
        pytest.param(False, 0.8, FileNotFoundError, id="source-absente"),
        pytest.param(True, 9.0, ValueError, id="fin-au-dela-de-la-duree"),
    ],
)
def test_une_entree_invalide_est_refusee_sans_laisser_de_fichier(
    clip_anime, tmp_path, source_existe, fin, erreur
):
    """Un échec ne doit JAMAIS laisser de GIF partiel derrière lui.

    La fonction est propriétaire du chemin qu'on lui confie : elle le supprime
    si elle n'a pas pu le remplir, y compris quand l'appelant l'avait déjà créé
    — c'est le cas du mkstemp côté composant.
    """
    source = clip_anime if source_existe else tmp_path / "absente.mp4"
    sortie = tmp_path / "sortie.gif"
    sortie.touch()  # comme le ferait mkstemp avant l'appel

    with pytest.raises(erreur):
        convertir_en_gif(source, sortie, ConversionParams(0.0, fin, fps=5))

    assert not sortie.exists()


@pytest.mark.parametrize("nom_source, attendu", NOMS_A_ASSAINIR)
def test_le_nom_de_telechargement_est_assaini(nom_source, attendu):
    """Ce nom part dans un en-tête Content-Disposition, que Streamlit compose
    par interpolation entre guillemets : il ne doit contenir ni séparateur de
    chemin, ni guillemet, ni retour ligne."""
    nom = nom_fichier_gif(nom_source)

    assert nom == attendu
    assert not set(nom) & set('"\\/\r\n')
