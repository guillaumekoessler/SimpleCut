"""Point d'entrée Streamlit — routeur multipage de SimpleCut."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import streamlit as st

st.set_page_config(
    page_title="SimpleCut",
    layout="centered",
    page_icon="👋",
)

home = st.Page(
    "src/pages/Home.py",
    title="Accueil",
    icon="🏠",
    default=True,
)
video_to_gif = st.Page(
    "src/pages/VideoToGifs.py",
    title="Vidéo → GIF",
    icon="🎥",
)

pages = [home]
if st.session_state.get("uploaded_video") is not None:
    pages.append(video_to_gif)
else:
    st.sidebar.text("Veuillez importer une vidéo")

pg = st.navigation(pages)
pg.run()
