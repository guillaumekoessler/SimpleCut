"""Extraction cachée de vignettes : décodage réel sur le clip de session."""

import shutil

import numpy as np
import pytest

from tests.donnees import VERT
from utils.Frames import extraire_vignette


def test_retourne_une_frame_rgb_uint8(clip_reel):
    vignette = extraire_vignette(str(clip_reel), "id-test", 0.5)

    assert isinstance(vignette, np.ndarray)
    assert vignette.dtype == np.uint8
    # Le clip fait 64x48 < 480 : thumbnail() ne doit JAMAIS agrandir.
    assert vignette.shape == (48, 64, 3)


def test_le_contenu_est_bien_decode(clip_reel):
    # ColorClip (200, 30, 30) : rouge dominant, même après l'encodage H.264.
    vignette = extraire_vignette(str(clip_reel), "id-test", 0.5)

    assert vignette[..., 0].mean() > 150  # canal R
    assert vignette[..., 1].mean() < 80  # canal G


def test_fichier_illisible_leve_oserror(tmp_path):
    """On verifie qu'un fichier comrompu ne soit pas lu"""
    faux = tmp_path / "faux.mov"
    faux.write_bytes(b"\x00" * 16)

    with pytest.raises(OSError):
        extraire_vignette(str(faux), "id-faux", 0.0)


def test_largeur_max_invalide(clip_reel):
    """on test que largeur max soit positive"""
    with pytest.raises(ValueError):
        extraire_vignette(str(clip_reel), "id-test", 0.5, largeur_max=0)


def test_file_id_fait_partie_de_la_cle_de_cache(clip_reel, tmp_path, fabrique_clip):
    """Un chemin de tempfile peut être recyclé par l'OS : file_id désambiguïse.

    Scénario complet : même chemin, contenu remplacé (rouge → vert).
    Avec le MÊME file_id le cache ressert l'ancienne frame (rouge) ;
    avec un NOUVEAU file_id la vidéo est re-décodée (vert).
    """
    chemin = tmp_path / "recycle.mp4"
    shutil.copy(clip_reel, chemin)
    frame_rouge = extraire_vignette(str(chemin), "upload-1", 0.5)

    fabrique_clip(chemin, VERT)  # même chemin, autre contenu

    meme_id = extraire_vignette(str(chemin), "upload-1", 0.5)
    autre_id = extraire_vignette(str(chemin), "upload-2", 0.5)

    assert np.array_equal(meme_id, frame_rouge)  # cache : l'ancienne frame
    assert autre_id[..., 1].mean() > 150  # re-décodée : le vert domine
