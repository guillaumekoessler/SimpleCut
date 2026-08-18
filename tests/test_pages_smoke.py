import pytest

from tests.donnees import CALAGES_REFERENCE

PAGES = ["src/pages/Home.py", "src/pages/VideoToGifs.py"]


# ---------------------------------------------------------------------------
# (a) Le filet : les pages s'importent et s'exécutent
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("page", PAGES)
def test_la_page_se_charge_sans_video(page, rendre_page):
    """Attrape l'ImportError qu'un nettoyage de Dimensions.py peut introduire.

    L'absence d'exception est affirmée par rendre_page : rendre EST le test.
    """
    rendre_page(page)


# ---------------------------------------------------------------------------
# (b) L'acceptation : les poids de l'aperçu suivent le ratio
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("page", PAGES)
@pytest.mark.parametrize("largeur, hauteur, poids", CALAGES_REFERENCE)
def test_apercu_suit_le_calage(
    page, largeur, hauteur, poids, fabrique_video, rendre_page, poids_apercu
):
    """ROUGE → VERT : les [2,3,2] et [1,2,1] codés en dur suivent le ratio.

    ⚠️ Asymétrie entre les deux pages, en portrait :
      - Home.py      : VERT avant ET après ([2,3,2] donnait déjà cette valeur).
                       C'est un garde-fou de non-régression, pas une preuve.
      - VideoToGifs  : ROUGE avant ([1,2,1] → 0.5), VERT après. Vraie preuve.
    """
    at = rendre_page(page, uploaded_video=fabrique_video(largeur, hauteur))

    assert poids_apercu(at) == pytest.approx(poids)


@pytest.mark.parametrize("page", PAGES)
def test_apercu_invariant_a_l_echelle(page, fabrique_video, rendre_page, poids_apercu):
    """1080x1920 et 720x1280 doivent produire exactement le même aperçu."""
    petit = poids_apercu(rendre_page(page, uploaded_video=fabrique_video(720, 1280)))
    grand = poids_apercu(rendre_page(page, uploaded_video=fabrique_video(1080, 1920)))
    assert petit == pytest.approx(grand)
