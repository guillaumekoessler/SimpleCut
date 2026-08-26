"""Panneau GIF : l'aperçu survit, l'identité pilote, les boutons sont centrés."""

import tempfile

import pytest
from streamlit.proto.Block_pb2 import Block as BlocProto

FIN_INITIALE = 0.8
FPS_TEST = 5


@pytest.fixture(autouse=True)
def _temporaires_isoles(tmp_path, monkeypatch):
    """Les GIFs produits atterrissent dans tmp_path, pas dans /tmp.

    Le panneau passe par tempfile.mkstemp. Sans cette redirection, chaque test
    laisserait ses GIFs dans le dossier temporaire du système : seule
    l'éviction du cache les nettoie, or le cache meurt avec l'AppTest.
    """
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))


def _app(video):
    # Import DANS le corps : obligatoire pour AppTest.from_function, qui
    # ré-exécute le SOURCE de cette fonction comme un script isolé. Pour la
    # même raison les constantes du module ci-dessus sont hors de portée ici :
    # 0.8 et 5 doivent être écrits en dur (et rester alignés sur elles).
    import streamlit as st

    from components.GifPanel import panneau_gif
    from utils.GifClasses import ConversionParams

    # Un slider pour faire varier les paramètres — c'est le geste de
    # l'utilisateur qui faisait disparaître l'aperçu.
    fin = st.slider("Fin", 0.1, 0.9, 0.8, step=0.1)
    panneau_gif(video, ConversionParams(0.0, fin, fps=5))


def _gif_en_cache(at, video, fin: float):
    """L'entrée de cache correspondant à ces paramètres, ou None.

    On interroge le cache par son API publique plutôt que de lire le rendu :
    c'est le seul moyen d'affirmer qu'aucune REgénération n'a eu lieu, deux
    GIFs successifs étant écrits dans deux tempfiles différents.
    """
    from utils.GifClasses import ConversionParams

    cle = (video.file_id, ConversionParams(0.0, fin, fps=FPS_TEST))
    return at.session_state["cache_gifs"].obtenir(cle)


def test_l_apercu_survit_a_un_rerun(rendre_app, video_reelle):
    """LE bug rapporté : « l'aperçu disparaît si on rechange le slider ».

    Cause : l'affichage était imbriqué dans le bloc qui consommait la demande
    de génération, donc rendu une seule fois, pendant le run qui suivait le
    clic. Ici, un simple rerun suffisait à tout effacer.
    """
    at = rendre_app(_app, args=(video_reelle,))

    at.button[0].click().run()
    assert not at.exception
    assert at.get("imgs"), "le GIF doit s'afficher après la génération"
    assert at.get("download_button")

    at.run()  # le rerun qui faisait tout disparaître

    assert not at.exception
    assert at.get("imgs"), "l'aperçu doit survivre à un rerun"
    assert at.get("download_button")


def test_changer_les_parametres_masque_l_apercu_puis_le_restitue_sans_regenerer(
    rendre_app, video_reelle
):
    """La règle d'identité : l'aperçu ne disparaît QUE si (file_id, params) change.

    Et le corollaire demandé : revenir sur les mêmes paramètres ressert le GIF
    déjà produit — même fichier, aucun nouveau passage par MoviePy, pas même un
    clic à redonner.
    """
    at = rendre_app(_app, args=(video_reelle,))
    at.button[0].click().run()
    chemin_initial = _gif_en_cache(at, video_reelle, FIN_INITIALE).chemin

    at.slider[0].set_value(0.5).run()  # on change les paramètres
    assert not at.exception

    # on revient aux paramètres d'origine
    at.slider[0].set_value(FIN_INITIALE).run()

    assert not at.exception
    assert at.get("imgs"), "mêmes paramètres : l'aperçu doit revenir"
    assert _gif_en_cache(at, video_reelle, FIN_INITIALE).chemin == chemin_initial
