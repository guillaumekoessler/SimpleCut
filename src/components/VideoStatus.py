from __future__ import annotations

import streamlit as st

from utils.VideoClasses import UploadedVideo


def afficher_statut_video() -> None:
    """
    Statut global de la vidéo chargée, affiché dans la barre latérale.
    Objectif : Afficher dans la sidebar l'état de la vidéo en session, sur toutes les pages.
    """
    video: UploadedVideo | None = st.session_state.get("uploaded_video")
    with st.sidebar:
        if video is not None:
            st.success(f"🎬 {video.name} · {video.duration:.0f} s")
        else:
            st.caption("Aucune vidéo chargée")
