"""Extraction cachée de vignettes vidéo (frame décodée → miniature RGB)."""

from __future__ import annotations

import numpy as np
import streamlit as st
from moviepy import VideoFileClip
from PIL import Image

# Résolution de DÉCODAGE des vignettes (~2× la largeur d'affichage d'une
# demi-colonne : net sur écran Retina, sans stocker des frames 1080p dans le
# cache). Ce n'est PAS une largeur d'affichage — le calage visuel reste
# l'affaire exclusive de utils.Layout.
LARGEUR_MAX_EXTRACTION = 480

# Plafond mémoire du cache : 64 × (480×270×3 octets ≈ 0,4 Mo) ≈ 25 Mo.
_MAX_VIGNETTES_EN_CACHE = 64


@st.cache_data(max_entries=_MAX_VIGNETTES_EN_CACHE, show_spinner=False)
def extraire_vignette(
    chemin: str, file_id: str, t: float, largeur_max: int = LARGEUR_MAX_EXTRACTION
) -> np.ndarray:
    """Frame RGB de la vidéo à l'instant t, réduite à largeur_max pixels.

    Chaque appel non caché ouvre puis referme le clip : ~75-215 ms mesurés sur
    une 1080p. On n'utilise PAS de clip persistant (st.cache_resource) : le
    lecteur ffmpeg de MoviePy n'est pas thread-safe entre sessions Streamlit.

    Args:
        chemin: Chemin du fichier vidéo. `str` et non Path : il fait partie
            de la clé de cache.
        file_id: Identité de l'upload. Dans la signature UNIQUEMENT pour la
            clé de cache : un chemin de tempfile peut être réutilisé par l'OS
            après suppression, le file_id lève l'ambiguïté.
        t: Instant en secondes. INVARIANT : t passe TOUJOURS par
            temps_vignette() en amont — c'est lui qui arrondit (clé de cache
            stable) et borne t avant la dernière frame. Un t brut créerait
            une entrée de cache par position de slider et pourrait faire
            lire ffmpeg au-delà du fichier.
        largeur_max: Largeur maximale de la miniature (> 0, jamais agrandie).

    Returns:
        np.ndarray (H, W, 3) uint8 avec W <= largeur_max, ratio préservé.

    Raises:
        ValueError: Si largeur_max <= 0.
        OSError: Fichier absent, illisible ou corrompu (propagée telle
            quelle : c'est à l'appelant de décider quoi afficher).
    """
    if largeur_max <= 0:
        raise ValueError(f"largeur_max doit être > 0, reçu : {largeur_max!r}")

    with VideoFileClip(chemin) as clip:
        frame = clip.get_frame(t)

    image = Image.fromarray(frame)
    # thumbnail() réduit EN PLACE en préservant le ratio, et n'agrandit
    # jamais — contrairement à resize() qui déformerait ou upscalerait.
    image.thumbnail((largeur_max, largeur_max))
    return np.asarray(image)
