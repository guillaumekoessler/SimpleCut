"""Composant vignettes de bornes : rendu headless via AppTest."""

from streamlit.testing.v1 import AppTest


def _app(video, debut, fin):
    # Import DANS le corps : obligatoire pour AppTest.from_function.
    from components.FramePreview import afficher_vignettes_bornes

    afficher_vignettes_bornes(video, debut, fin)


def test_affiche_les_deux_vignettes(video_reelle):
    at = AppTest.from_function(_app, args=(video_reelle, 0.0, 0.9))
    at.run()

    assert not at.exception
    images = at.get("imgs")
    vignettes = [i for e in at.get("imgs") for i in e.proto.imgs]
    assert [v.caption for v in vignettes] == ["Début · 0.0 s", "Fin · 0.9 s"]


def test_video_illisible_affiche_un_caption_sans_planter(fausse_video):
    # fausse_video = 16 octets de zéros : MoviePy doit échouer, pas la page.
    at = AppTest.from_function(_app, args=(fausse_video(64, 48), 0.0, 0.5))
    at.run()

    assert not at.exception
    assert len(at.get("imgs")) == 0
    assert any("indisponibles" in c.value for c in at.caption)
