from pathlib import Path

import numpy as np
from streamlit.testing.v1 import AppTest

from utils.VideoClasses import UploadedVideo


def _app():
    # Import DANS le corps : obligatoire pour AppTest.from_function.
    from components.VideoStatus import afficher_statut_video

    afficher_statut_video()


def _fausse_video(nom: str, duree: float) -> UploadedVideo:
    # UploadedVideo est frozen/slots : les 9 champs sont requis.
    # VideoStatus ne lit que name / duration / thumbnail ; le reste = valeurs bidon.
    return UploadedVideo(
        path=Path("/tmp/fake.mov"),
        name=nom,
        duration=duree,
        width=10,
        height=10,
        fps=30.0,
        size_bytes=123,
        file_id="test",
        thumbnail=np.zeros((10, 10, 3), dtype=np.uint8),  # frame RGB minimale
    )


def test_statut_sans_video_affiche_la_caption():
    at = AppTest.from_function(_app)
    at.run()
    assert not at.exception
    assert len(at.sidebar.success) == 0
    assert at.sidebar.caption[0].value == "Aucune vidéo chargée"


def test_statut_avec_video():
    at = AppTest.from_function(_app)
    at.session_state["uploaded_video"] = _fausse_video("ma_video.mov", 12.0)
    at.run()

    assert not at.exception
    assert len(at.sidebar.success) == 1
    banniere = at.sidebar.success[0]

    assert "ma_video.mov" in banniere.value
    assert "12" in banniere.value
