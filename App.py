"""Page d'accueil de l'application Video to GIF."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import streamlit as st

import tempfile
from dataclasses import dataclass
from pathlib import Path

from moviepy import VideoFileClip

st.set_page_config(page_title="SimpleCut", layout="centered")


# A déplacer


@dataclass
class UploadedVideo:
    """Résultat d'un upload vidéo validé."""

    path: Path
    duration: float


def video_uploader(
    label: str = "Importez votre vidéo (.mov)",
) -> UploadedVideo | None:
    """ """

    uploaded_file = st.file_uploader(
        label,
        type=".mov",
        accept_multiple_files=False,
        label_visibility="collapsed",
    )

    if uploaded_file is None:
        return None

    with tempfile.NamedTemporaryFile(delete=False, suffix=".mov") as tmp_video:
        tmp_video.write(uploaded_file.read())
        video_path = Path(tmp_video.name)

    with VideoFileClip(str(video_path)) as clip:
        duration = float(clip.duration)

    return UploadedVideo(path=Path(tmp_video.name), duration=duration)


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("Video to GIF", text_alignment="center")
st.caption("Convertissez une vidéo .mov en GIF animé", text_alignment="center")
st.divider()

# ---------------------------------------------------------------------------
# Upload section
# ---------------------------------------------------------------------------
with st.container(border=True):
    st.caption("IMPORT")
    video = video_uploader()

# ---------------------------------------------------------------------------
# Main content (after upload)
# ---------------------------------------------------------------------------
if video is not None:
    # ── Preview card ──────────────────────────────────────
    with st.container(border=True):
        st.caption("APERÇU")
        st.video(str(video.path))
else:
    st.info("Importez une vidéo .mov pour commencer.", icon="🎬")
