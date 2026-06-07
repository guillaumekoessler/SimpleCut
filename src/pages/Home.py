"""Page d'accueil de SimpleCut."""

from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st
from moviepy import VideoFileClip

from utils.VideoClasses import UploadedVideo


def _build_uploaded_video(uploaded_file) -> UploadedVideo:
    with tempfile.NamedTemporaryFile(delete=False) as tmp_video:
        tmp_video.write(uploaded_file.read())
        video_path = Path(tmp_video.name)

    with VideoFileClip(str(video_path)) as clip:
        duration = float(clip.duration)

    return UploadedVideo(
        path=video_path,
        duration=duration,
        file_id=uploaded_file.file_id,
    )


def video_uploader(
    label: str = "Importez votre vidéo",
) -> UploadedVideo | None:
    seed = st.session_state.get("uploader_seed", 0)
    uploaded_file = st.file_uploader(
        label,
        type="video/*",
        accept_multiple_files=False,
        label_visibility="collapsed",
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
