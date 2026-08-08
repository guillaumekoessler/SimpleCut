from pathlib import Path

import numpy as np
import pytest
from streamlit.testing.v1 import AppTest

from utils.VideoClasses import UploadedVideo

PAGES = ["src/pages/Home.py", "src/pages/VideoToGifs.py"]

RACINE = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# (a) Le filet : les pages s'importent et s'exécutent
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("page", PAGES)
def test_la_page_se_charge_sans_video(page):
    """Attrape l'ImportError qu'un nettoyage de Dimensions.py peut introduire."""
    at = AppTest.from_file(str(RACINE / page))
    at.run()
    assert not at.exception


# ---------------------------------------------------------------------------
# (b) L'acceptation : les poids de l'aperçu suivent le ratio
# ---------------------------------------------------------------------------
@pytest.fixture
def fausse_video(tmp_path):
    """Fabrique un UploadedVideo pointant sur un fichier bidon de 16 octets.

    st.video ne décode rien : il lit les octets et les transmet au navigateur.
    Aucune vraie vidéo n'est nécessaire pour rendre l'aperçu.
    """
    chemin = tmp_path / "fausse.mov"
    chemin.write_bytes(b"\x00" * 16)

    def _fabriquer(largeur: int, hauteur: int) -> UploadedVideo:
        return UploadedVideo(
            path=chemin,
            name="fausse.mov",
            duration=10.0,
            width=largeur,
            height=hauteur,
            fps=30.0,
            size_bytes=16,
            file_id="test-file-id",
            thumbnail=np.zeros((10, 10, 3), dtype=np.uint8),
        )

    return _fabriquer


def _triplet_apercu(at):
    """Localise l'aperçu : la seule colonne non vide entourée de deux colonnes vides.

    On n'indexe PAS en aveugle : chaque page rend 7 colonnes dans un ordre
    différent, et ce nombre changera. L'invariant robuste est structurel.
    """
    cols = at.get("column")
    enfants = [len(c.children) for c in cols]
    milieux = [
        i
        for i in range(1, len(cols) - 1)
        if enfants[i - 1] == 0 and enfants[i] > 0 and enfants[i + 1] == 0
    ]
    assert len(milieux) == 1, f"triplet non identifiable : {enfants}"
    i = milieux[0]
    return [cols[j].proto.weight for j in (i - 1, i, i + 1)]


def _rendre(page: str, video: UploadedVideo) -> AppTest:
    at = AppTest.from_file(str(RACINE / page))
    at.session_state["uploaded_video"] = video
    at.run()
    assert not at.exception
    return at


@pytest.mark.parametrize("page", PAGES)
def test_apercu_paysage_utilise_toute_la_largeur(page, fausse_video):
    """ROUGE → VERT : [2,3,2] et [1,2,1] en dur deviennent (0.1, 0.8, 0.1)."""
    at = _rendre(page, fausse_video(640, 360))
    assert _triplet_apercu(at) == pytest.approx([0.1, 0.8, 0.1])


@pytest.mark.parametrize("page", PAGES)
def test_apercu_paysage_utilise_toute_la_largeur(page, fausse_video):
    """ROUGE → VERT : [2,3,2] et [1,2,1] en dur deviennent (0.1, 0.8, 0.1)."""
    at = _rendre(page, fausse_video(640, 360))
    assert _triplet_apercu(at) == pytest.approx([0.1, 0.8, 0.1])


@pytest.mark.parametrize("page", PAGES)
def test_apercu_portrait_reste_etroit(page, fausse_video):
    """Le portrait doit valoir (2/7, 3/7, 2/7).

    ⚠️ Asymétrie entre les deux pages :
      - Home.py      : VERT avant ET après ([2,3,2] donnait déjà cette valeur).
                       C'est un garde-fou de non-régression, pas une preuve.
      - VideoToGifs  : ROUGE avant ([1,2,1] → 0.5), VERT après. Vraie preuve.
    """
    at = _rendre(page, fausse_video(720, 1280))
    assert _triplet_apercu(at) == pytest.approx([2 / 7, 3 / 7, 2 / 7])


@pytest.mark.parametrize("page", PAGES)
def test_apercu_invariant_a_l_echelle(page, fausse_video):
    """1080x1920 et 720x1280 doivent produire exactement le même aperçu."""
    petit = _triplet_apercu(_rendre(page, fausse_video(720, 1280)))
    grand = _triplet_apercu(_rendre(page, fausse_video(1080, 1920)))
    assert petit == pytest.approx(grand)
