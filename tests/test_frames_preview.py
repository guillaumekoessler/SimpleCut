"""Composant vignettes de bornes : rendu headless via AppTest."""


def _app(video, debut, fin):
    # Import DANS le corps : obligatoire pour AppTest.from_function.
    from components.FramePreview import afficher_vignettes_bornes

    afficher_vignettes_bornes(video, debut, fin)


def test_affiche_les_deux_vignettes(video_reelle, rendre_app, legendes_vignettes):
    at = rendre_app(_app, args=(video_reelle, 0.0, 0.9))

    assert legendes_vignettes(at) == ["Début · 0.0 s", "Fin · 0.9 s"]


def test_video_illisible_affiche_un_caption_sans_planter(
    fabrique_video, rendre_app, legendes_vignettes
):
    # fabrique_video() = 16 octets de zéros : MoviePy doit échouer, pas la page.
    at = rendre_app(_app, args=(fabrique_video(64, 48), 0.0, 0.5))

    assert legendes_vignettes(at) == []
    assert any("indisponibles" in c.value for c in at.caption)
