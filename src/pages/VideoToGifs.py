import streamlit as st
from moviepy import VideoFileClip
import tempfile
from pathlib import Path


from components.VideoStatus import afficher_statut_video
from utils.VideoClasses import UploadedVideo
from utils.GifClasses import ConversionParams

afficher_statut_video()

current: UploadedVideo | None = st.session_state.get("uploaded_video")


def _convert_video_to_gif(
    video_path: Path,
    output_path: Path,
    params: ConversionParams,
) -> Path:
    """Convertit un segment de vidéo en GIF animé.

    Args:
        video_path: Chemin vers la vidéo source (.mov).
        output_path: Chemin de sortie du GIF.
        params: Paramètres de conversion.

    Returns:
        Le chemin du GIF généré.

    Raises:
        FileNotFoundError: Si la vidéo source n'existe pas.
        ValueError: Si les paramètres dépassent la durée de la vidéo.
    """
    if not video_path.exists():
        raise FileNotFoundError(f"Fichier source introuvable : {video_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with VideoFileClip(str(video_path)) as clip:
        if params.end_time > clip.duration:
            raise ValueError(
                f"end_time ({params.end_time}s) dépasse la durée de la vidéo ({clip.duration}s)"
            )

        subclip = clip.subclipped(params.start_time, params.end_time)

        if params.resize_factor < 1.0:
            subclip = subclip.resized(params.resize_factor)

        subclip.write_gif(str(output_path), fps=params.fps, logger=None)

    return output_path


st.video(str(current.path))

# selection des paramètres de reformating de la video
with st.container(border=True):
    st.caption("PARAMÈTRES")

    start_time, end_time = st.slider(
        "Intervalle",
        min_value=0.0,
        max_value=float(current.duration),
        value=(0.0, min(5.0, float(current.duration))),
        step=0.1,
        format="%.1fs",
    )

    col1, col2 = st.columns(2)
    with col1:
        fps = st.slider("FPS", 5, 30, 15, 5)
    with col2:
        resize_factor = st.slider("Échelle", 0.1, 1.0, 1.0, step=0.1)

    st.divider()
    st.caption(
        f"Segment : {end_time - start_time:.1f}s · FPS : {fps} · Échelle : {resize_factor}"
    )

# création du gif en fonction des paramètres séléctionnés

st.button("Création du Gif", on_click=cancel_replacing)

st.write("Hello")
