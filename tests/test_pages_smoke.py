import pytest

PAGES = ["src/pages/Home.py", "src/pages/VideoToGifs.py"]


# ---------------------------------------------------------------------------
# (a) Le filet : les pages s'importent et s'exécutent
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("page", PAGES)
def test_la_page_se_charge_sans_video(page, rendre_page):
    """Attrape l'ImportError qu'un nettoyage de Dimensions.py peut introduire."""
    at = rendre_page(page)
    assert not at.exception


# ---------------------------------------------------------------------------
# (b) L'acceptation : les poids de l'aperçu suivent le ratio
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("page", PAGES)
def test_apercu_paysage_utilise_toute_la_largeur(
    page, fausse_video, rendre_page, poids_apercu
):
    """ROUGE → VERT : [2,3,2] et [1,2,1] en dur deviennent (0.1, 0.8, 0.1)."""
    at = rendre_page(page, uploaded_video=fausse_video(640, 360))
    assert not at.exception
    assert poids_apercu(at) == pytest.approx([0.1, 0.8, 0.1])


@pytest.mark.parametrize("page", PAGES)
def test_apercu_portrait_reste_etroit(page, fausse_video, rendre_page, poids_apercu):
    """Le portrait doit valoir (2/7, 3/7, 2/7).

    ⚠️ Asymétrie entre les deux pages :
      - Home.py      : VERT avant ET après ([2,3,2] donnait déjà cette valeur).
                       C'est un garde-fou de non-régression, pas une preuve.
      - VideoToGifs  : ROUGE avant ([1,2,1] → 0.5), VERT après. Vraie preuve.
    """
    at = rendre_page(page, uploaded_video=fausse_video(720, 1280))
    assert not at.exception
    assert poids_apercu(at) == pytest.approx([2 / 7, 3 / 7, 2 / 7])


@pytest.mark.parametrize("page", PAGES)
def test_apercu_invariant_a_l_echelle(page, fausse_video, rendre_page, poids_apercu):
    """1080x1920 et 720x1280 doivent produire exactement le même aperçu."""
    petit = poids_apercu(rendre_page(page, uploaded_video=fausse_video(720, 1280)))
    grand = poids_apercu(rendre_page(page, uploaded_video=fausse_video(1080, 1920)))
    assert petit == pytest.approx(grand)
