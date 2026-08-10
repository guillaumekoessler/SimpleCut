def _app():
    # Import DANS le corps : obligatoire pour AppTest.from_function.
    from components.VideoStatus import afficher_statut_video

    afficher_statut_video()


def test_statut_sans_video_affiche_la_caption(rendre_app):
    at = rendre_app(_app)

    assert not at.exception
    assert len(at.sidebar.success) == 0
    assert at.sidebar.caption[0].value == "Aucune vidéo chargée"


def test_statut_avec_video(rendre_app, fabrique_video):
    # VideoStatus ne lit que name / duration / thumbnail : on ne surcharge que ça.
    at = rendre_app(_app, uploaded_video=fabrique_video(nom="ma_video.mov", duree=12.0))

    assert not at.exception
    assert len(at.sidebar.success) == 1
    banniere = at.sidebar.success[0]

    assert "ma_video.mov" in banniere.value
    assert "12" in banniere.value
