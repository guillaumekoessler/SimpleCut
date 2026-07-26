from __future__ import annotations

import streamlit as st

from utils.Dimensions import LARGEUR_VIGNETTE_SIDEBAR
from utils.VideoClasses import UploadedVideo


def afficher_statut_video() -> None:
    """
    Statut global de la vidéo chargée, affiché dans la barre latérale.
    Objectif : Afficher dans la sidebar l'état de la vidéo en session, sur toutes les pages.
    """
    video: UploadedVideo | None = st.session_state.get("uploaded_video")

    with st.sidebar:
        if video is not None:
            col_vignette, col_infos = st.columns([1, 3], vertical_alignment="center")
            with col_vignette:
                st.image(video.thumbnail, width=LARGEUR_VIGNETTE_SIDEBAR)
            with col_infos:
                st.success(f"{video.name} · {video.duration:.0f} s")
        else:
            st.caption("Aucune vidéo chargée")
