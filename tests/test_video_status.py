def _app():
    # Import DANS le corps : obligatoire pour AppTest.from_function.
    from components.VideoStatus import afficher_statut_video

    afficher_statut_video()


def test_statut_sans_video_affiche_la_caption(rendre_app):
    at = rendre_app(_app)

    assert not at.exception
    assert len(at.sidebar.success) == 0
    assert at.sidebar.caption[0].value == "Aucune vidéo chargée"


def test_statut_avec_video(rendre_app, video_reelle):
    # VideoStatus ne lit que name / duration / thumbnail : la vidéo adossée au
    # clip réel (mini.mp4, 1 s) suffit — rien n'est décodé ici.
    at = rendre_app(_app, uploaded_video=video_reelle)

    assert not at.exception
    assert len(at.sidebar.success) == 1
    banniere = at.sidebar.success[0]

    assert "mini.mp4" in banniere.value
    assert "1 s" in banniere.value
