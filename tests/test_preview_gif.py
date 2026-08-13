"""Couche pure de l'aperçu d'intervalle : bornes de boucle et temps de vignette."""

import math

import pytest

from utils.PreviewGif import PAS_INTERVALLE, bornes_boucle_video, temps_vignette


# ---------------------------------------------------------------------------
# temps_vignette : arrondi au pas du slider + bornage à la dernière frame
# ---------------------------------------------------------------------------
class TestTempsVignette:
    def test_arrondit_au_pas_du_slider(self):
        assert temps_vignette(3.14159, duree=10.0, fps=30.0) == pytest.approx(3.1)

    def test_un_multiple_du_pas_reste_inchange(self):
        assert temps_vignette(2.5, duree=10.0, fps=30.0) == pytest.approx(2.5)

    def test_normalise_le_bruit_flottant(self):
        # 0.1 + 0.2 == 0.30000000000000004 : la clé de cache doit être stable.
        assert temps_vignette(0.1 + 0.2, duree=10.0, fps=30.0) == 0.3

    def test_borne_a_la_derniere_frame(self):
        # Demander la frame à t == duree fait lire ffmpeg au-delà de la
        # dernière frame → on recule d'une frame.
        assert temps_vignette(10.0, duree=10.0, fps=30.0) == pytest.approx(
            10.0 - 1.0 / 30.0
        )

    def test_borne_le_negatif_a_zero(self):
        with pytest.raises(ValueError):
            temps_vignette(-2.0, duree=10.0, fps=30.0) == 0.0

    def test_video_plus_courte_qu_une_frame(self):
        # duree - 1/fps < 0 : le plancher 0 doit gagner, pas un temps négatif.
        assert temps_vignette(0.5, duree=0.02, fps=30.0) == 0.0

    @pytest.mark.parametrize("duree", [0.0, -1.0, math.nan, math.inf])
    def test_duree_invalide(self, duree):
        with pytest.raises(ValueError):
            temps_vignette(1.0, duree=duree, fps=30.0)

    @pytest.mark.parametrize("fps", [0.0, -30.0, math.nan])
    def test_fps_invalide(self, fps):
        with pytest.raises(ValueError):
            temps_vignette(1.0, duree=10.0, fps=fps)


# ---------------------------------------------------------------------------
# bornes_boucle_video : st.video tronque à la seconde (int32 dans le proto),
# la boucle doit donc ENGLOBER la sélection, jamais l'amputer.
# ---------------------------------------------------------------------------
class TestBornesBoucleVideo:
    def test_englobe_la_selection(self):
        assert bornes_boucle_video(1.2, 4.5, duree=10.0) == (1, 5)

    def test_bornes_entieres_inchangees(self):
        assert bornes_boucle_video(2.0, 5.0, duree=10.0) == (2, 5)

    def test_selection_reduite_a_un_point(self):
        # Boucle d'au moins 1 s, sinon st.video reçoit debut == fin.
        assert bornes_boucle_video(2.0, 2.0, duree=10.0) == (2, 3)

    def test_selection_sub_seconde(self):
        assert bornes_boucle_video(2.3, 2.4, duree=10.0) == (2, 3)

    def test_fin_a_la_duree(self):
        assert bornes_boucle_video(9.5, 10.0, duree=10.0) == (9, 10)

    def test_depasser_la_duree_reelle_est_tolere(self):
        # ceil(9.5) == 10 > 9.7 : sans danger, le frontend gère l'événement
        # `ended` et reboucle vers start_time même si end_time est inatteignable.
        assert bornes_boucle_video(8.2, 9.5, duree=9.7) == (8, 10)

    def test_debut_negatif(self):
        with pytest.raises(ValueError):
            bornes_boucle_video(-0.1, 4.0, duree=10.0)

    def test_fin_avant_debut(self):
        with pytest.raises(ValueError):
            bornes_boucle_video(5.0, 4.0, duree=10.0)

    def test_fin_au_dela_de_la_duree(self):
        with pytest.raises(ValueError):
            bornes_boucle_video(0.0, 10.1, duree=10.0)

    @pytest.mark.parametrize("duree", [0.0, -5.0, math.nan])
    def test_duree_invalide(self, duree):
        with pytest.raises(ValueError):
            bornes_boucle_video(0.0, 1.0, duree=duree)

    def test_borne_non_finie(self):
        with pytest.raises(ValueError):
            bornes_boucle_video(math.nan, 1.0, duree=10.0)


def test_le_pas_du_slider_est_la_source_unique():
    """La page importe cette constante : la changer ICI change le slider."""
    assert PAS_INTERVALLE == 0.1
