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

    if cached is not None:
        cached.path.unlink(missing_ok=True)

    return _build_uploaded_video(uploaded_file)


def remove_video() -> None:
    cached: UploadedVideo | None = st.session_state.pop("uploaded_video", None)
    if cached is not None:
        cached.path.unlink(missing_ok=True)
    st.session_state.uploader_seed = st.session_state.get("uploader_seed", 0) + 1


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("SimplCut", text_alignment="center")
st.caption("Convertissez une vidéo .mov en GIF animé", text_alignment="center")
st.divider()

# ---------------------------------------------------------------------------
# Upload section
# ---------------------------------------------------------------------------
with st.container(border=True):
    st.caption("IMPORT")
    video = video_uploader()

if video is not None:
    first_upload = st.session_state.get("uploaded_video") is None
    st.session_state.uploaded_video = video
    if first_upload:
        st.rerun()

# ---------------------------------------------------------------------------
# Preview + remove
# ---------------------------------------------------------------------------
current: UploadedVideo | None = st.session_state.get("uploaded_video")
if current is not None:
    with st.container(border=True):
        st.caption("APERÇU")
        st.video(str(current.path))
        st.button("Supprimer la vidéo", on_click=remove_video)
else:
    st.info("Importez une vidéo pour commencer.", icon="🎬")
