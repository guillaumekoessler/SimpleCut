"""Extraction cachée de vignettes : décodage réel sur le clip de session."""

import shutil

import numpy as np
import pytest

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
