"""Page d'accueil de SimpleCut."""

from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st
from moviepy import VideoFileClip

from utils.VideoClasses import UploadedVideo


def video_uploader(
    label: str = "Importez votre vidéo",
) -> UploadedVideo | None:
    uploaded_file = st.file_uploader(
        label,
        type="video/*",
        accept_multiple_files=False,
        label_visibility="collapsed",
    )

    if uploaded_file is None:
        return None

    with tempfile.NamedTemporaryFile(delete=False) as tmp_video:
        tmp_video.write(uploaded_file.read())
        video_path = Path(tmp_video.name)

    with VideoFileClip(str(video_path)) as clip:
        duration = float(clip.duration)

    return UploadedVideo(path=video_path, duration=duration)


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

# ---------------------------------------------------------------------------
# Synchronisation avec st.session_state + rerun déclencheur de la nav
# ---------------------------------------------------------------------------
if video is not None:
    first_upload = st.session_state.get("uploaded_video") is None
    st.session_state.uploaded_video = video
    if first_upload:
        st.rerun()
elif st.session_state.get("uploaded_video") is not None:
    del st.session_state.uploaded_video
    st.rerun()

# ---------------------------------------------------------------------------
# Main content (after upload)
# ---------------------------------------------------------------------------
if video is not None:
    with st.container(border=True):
        st.caption("APERÇU")
        st.video(str(video.path))
else:
    st.info("Importez une vidéo pour commencer.", icon="🎬")
