"""Page VideoToGifs : le lecteur boucle sur l'intervalle du slider."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

PAGE = Path(__file__).parent.parent / "src" / "pages" / "VideoToGifs.py"


def _rendre(video) -> AppTest:
    at = AppTest.from_file(str(PAGE))
    at.session_state["uploaded_video"] = video
    at.run()
    assert not at.exception
    return at


def _proto_video(at):
    videos = at.get("video")
    assert len(videos) == 1
    return videos[0].proto


def test_le_lecteur_suit_le_slider(fausse_video):
    at = _rendre(fausse_video(640, 360))

    at.slider[0].set_value((1.2, 4.5)).run()
    assert not at.exception

    proto = _proto_video(at)
    # floor(1.2) → 1 et ceil(4.5) → 5 : la boucle ENGLOBE la sélection
    # (st.video tronque les bornes à la seconde entière).
    assert (proto.start_time, proto.end_time) == (1, 5)
    assert proto.loop


def test_les_vignettes_suivent_le_slider(video_reelle):
    """L'acceptation cœur du besoin : bouger le slider met à jour les bornes."""
    at = _rendre(video_reelle)

    at.slider[0].set_value((0.2, 0.8)).run()
    assert not at.exception

    legendes = [img.proto.imgs[0].caption for img in at.main.get("imgs")]
    assert legendes == ["Début · 0.2 s", "Fin · 0.8 s"]
