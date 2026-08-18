"""Page VideoToGifs : le lecteur boucle sur l'intervalle du slider."""

PAGE = "src/pages/VideoToGifs.py"


def test_le_lecteur_suit_le_slider(fabrique_video, rendre_page):
    at = rendre_page(PAGE, uploaded_video=fabrique_video(640, 360))

    at.slider[0].set_value((1.2, 4.5)).run()
    assert not at.exception  # ce run-là est déclenché ici, pas par rendre_page

    videos = at.get("video")
    assert len(videos) == 1
    proto = videos[0].proto

    # floor(1.2) → 1 et ceil(4.5) → 5 : la boucle ENGLOBE la sélection
    # (st.video tronque les bornes à la seconde entière).
    assert (proto.start_time, proto.end_time) == (1, 5)
    assert proto.loop


def test_les_vignettes_suivent_le_slider(video_reelle, rendre_page, legendes_vignettes):
    """L'acceptation cœur du besoin : bouger le slider met à jour les bornes."""
    at = rendre_page(PAGE, uploaded_video=video_reelle)

    at.slider[0].set_value((0.2, 0.8)).run()
    assert not at.exception  # ce run-là est déclenché ici, pas par rendre_page

    assert legendes_vignettes(at) == ["Début · 0.2 s", "Fin · 0.8 s"]
