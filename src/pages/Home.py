"""Page d'accueil de SimpleCut."""

from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st
from moviepy import VideoFileClip

from utils.VideoClasses import UploadedVideo
from components.VideoStatus import afficher_statut_video


def _build_uploaded_video(uploaded_file) -> UploadedVideo | None:
    with tempfile.NamedTemporaryFile(delete=False) as tmp_video:
        tmp_video.write(uploaded_file.read())
        video_path = Path(tmp_video.name)

    try:
        with VideoFileClip(str(video_path)) as clip:
            duration = float(clip.duration)
            width, height = clip.size
            fps = float(clip.fps)
            thumbnail = clip.get_frame(0)
    except Exception:
        # Fichier illisible : on nettoie le temporaire et on signale l'échec.
        video_path.unlink(missing_ok=True)
        st.error("Impossible de lire cette vidéo.")
        return None

    return UploadedVideo(
        path=video_path,
        name=uploaded_file.name,
        duration=duration,
        width=width,
        height=height,
        fps=fps,
        size_bytes=video_path.stat().st_size,
        file_id=uploaded_file.file_id,
        thumbnail=thumbnail,
    )


def video_uploader(
    label: str = "Importez votre vidéo",
) -> UploadedVideo | None:
    seed = st.session_state.get("uploader_seed", 0)
    uploaded_file = st.file_uploader(
        label,
        type="video/*",
        accept_multiple_files=False,
        label_visibility="hidden",
        key=f"home_video_uploader_{seed}",
    )

    cached: UploadedVideo | None = st.session_state.get("uploaded_video")

    if uploaded_file is None:
        return cached

    if cached is not None and cached.file_id == uploaded_file.file_id:
        return cached

    with st.spinner("Analyse de la vidéo…"):
        new_video = _build_uploaded_video(uploaded_file)

    if new_video is None:
        # Échec de lecture : on conserve la vidéo précédente telle quelle.
        return cached

    # On ne supprime l'ancien fichier qu'une fois le nouveau validé.
    if cached is not None:
        cached.path.unlink(missing_ok=True)

    st.toast("Vidéo importée ✅")
    return new_video


def remove_video() -> None:
    cached: UploadedVideo | None = st.session_state.pop("uploaded_video", None)
    if cached is not None:
        cached.path.unlink(missing_ok=True)
    st.session_state.replacing = False
    st.session_state.uploader_seed = st.session_state.get("uploader_seed", 0) + 1


def start_replacing() -> None:
    st.session_state.replacing = True


def cancel_replacing() -> None:
    st.session_state.replacing = False


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

afficher_statut_video()

st.title("SimplCut", text_alignment="center")
st.caption("Convertissez une vidéo .mov en GIF animé", text_alignment="center")
st.divider()

# ---------------------------------------------------------------------------
# Upload section
# ---------------------------------------------------------------------------
# on récupère la video si elle est deja chargée, on stock cela dans une variable "current"
current: UploadedVideo | None = st.session_state.get("uploaded_video")
replacing: bool = st.session_state.get("replacing", False)

with st.container(border=True):
    st.caption("IMPORT")

    if current is None or replacing:
        # État « pas de vidéo » (ou remplacement en cours) : on montre l'uploader.
        video = video_uploader()
        if replacing:
            st.button("Annuler", on_click=cancel_replacing)
        if video is not None and video is not current:
            # si une nouvelle video a été upload, on remplace l'ancienne
            st.session_state.uploaded_video = video
            st.session_state.replacing = False
            # obligation de rerun ici car rechargement complet des éléments : sidebar etc...
            st.rerun()

    else:
        # État « vidéo chargée » : carte de statut à la place de l'uploader.
        st.success(f"✅ {current.name} chargée — {current.duration:.1f} s")

        col_vignette, col_metriques = st.columns([1, 3], vertical_alignment="center")
        with col_vignette:
            st.image(current.thumbnail, width="stretch")
        with col_metriques:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Durée", f"{current.duration:.1f} s")
            m2.metric("Dimensions", f"{current.width}×{current.height}")
            m3.metric("FPS", f"{current.fps:.0f}")
            m4.metric("Poids", f"{current.size_bytes / 1_000_000:.1f} Mo")

        col_remplacer, col_supprimer = st.columns(2)
        col_remplacer.button("Remplacer", on_click=start_replacing, width="stretch")
        col_supprimer.button(
            "Supprimer la vidéo", on_click=remove_video, width="stretch"
        )

# ---------------------------------------------------------------------------
# Preview + remove
# ---------------------------------------------------------------------------
if current is not None:
    with st.container(border=True):
        st.caption("APERÇU")
        st.video(str(current.path))
else:
    st.info("Importez une vidéo pour commencer.", icon="🎬")
