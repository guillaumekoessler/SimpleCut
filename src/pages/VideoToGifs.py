import os
import tempfile
from pathlib import Path

import streamlit as st
from moviepy import VideoFileClip

from components.VideoStatus import afficher_statut_video
from utils.Dimensions import LARGEUR_APERCU_GIF, LARGEUR_APERCU_VIDEO
from utils.GifClasses import ConversionParams
from utils.VideoClasses import UploadedVideo

afficher_statut_video()

current: UploadedVideo | None = st.session_state.get("uploaded_video")

if current is None:
    st.info("Importez une vidéo pour commencer.", icon="🎬")
    st.stop()  # si aucune video rien Òne s'exécute : plus de crash


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


def _purger_ancien_gif() -> None:
    """Fonction permettant de supprimer un fichier gif si celui-ci existe"""
    resultat = st.session_state.get("gif_result")
    if resultat is not None:
        chemin, _ = resultat
        chemin.unlink(missing_ok=True)
        st.session_state.pop("gif_result", None)


# Fonction du callback pour la création du gif
def demander_generation(params: ConversionParams) -> None:
    st.session_state["gif_request"] = params


_, milieu, _ = st.columns([1, 2, 1])
with milieu:
    st.video(
        str(current.path),
        width=LARGEUR_APERCU_VIDEO,
        autoplay=True,
        muted=True,
        loop=True,
    )

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

# On vérifie que le temps de fin est bien supérieur au temps de début
segment_valide = end_time > start_time

params = None
if segment_valide:
    params = ConversionParams(
        start_time=start_time,
        end_time=end_time,
        fps=fps,
        resize_factor=resize_factor,
    )

    st.button(
        "Créer le GIF",
        on_click=demander_generation,
        args=(params,),  # tuple ! fige les params du run courant
        disabled=not segment_valide,  # confort UI ; la vraie protection est l'étape 2
    )

    if st.session_state.get("gif_request") is not None:
        params = st.session_state.pop("gif_request")  # consommé UNE fois

        # mkstemp + close : on ne garde pas de handle ouvert pendant que MoviePy écrit
        fd, chemin_str = tempfile.mkstemp(suffix=".gif")
        os.close(fd)
        output_path = Path(chemin_str)

        # nettoyer un éventuel GIF précédent
        _purger_ancien_gif()

        with st.status("Génération du GIF…") as status:
            try:
                _convert_video_to_gif(current.path, output_path, params)
            except (FileNotFoundError, ValueError) as e:
                output_path.unlink(missing_ok=True)  # pas de GIF partiel qui traîne
                status.update(label=f"Échec : {e}", state="error")
            else:
                # on rattache le résultat à L'IDENTITÉ de la vidéo courante
                st.session_state["gif_result"] = (output_path, current.file_id)
                status.update(label="GIF prêt ✅", state="complete")

        resultat = st.session_state.get("gif_result")
        if resultat is not None:
            chemin, file_id = resultat
            if file_id != current.file_id or not chemin.exists():
                # GIF issu d'une autre vidéo (ou temporaire disparu) → on purge
                chemin.unlink(missing_ok=True)
                st.session_state.pop("gif_result", None)
            else:
                octets = chemin.read_bytes()  # une seule lecture disque…
                _, milieu, _ = st.columns([1, 4, 1])
                with milieu:
                    st.image(octets)  # …réutilisée pour l'aperçu…
                st.download_button(  # …et pour le téléchargement
                    "Télécharger le GIF",
                    data=octets,
                    file_name=f"{Path(current.name).stem}.gif",  # (#6) pas .mov !
                    mime="image/gif",
                )


else:
    st.text("Veuillez élargir l'interval de temps.", text_alignment="center")
