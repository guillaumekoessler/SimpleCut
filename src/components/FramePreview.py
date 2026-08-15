"""Vignettes des bornes de l'intervalle sélectionné."""

from __future__ import annotations

import streamlit as st

from utils.Frames import extraire_vignette
from utils.PreviewGif import temps_vignette
from utils.VideoClasses import UploadedVideo


def afficher_vignettes_bornes(video: UploadedVideo, debut: float, fin: float) -> None:
    """Affiche côte à côte les frames de début et de fin de la sélection.

    À placer au-dessus du slider d'intervalle : l'utilisateur voit
    exactement sur quelles images son GIF commencera et finira.

    Les légendes affichent le temps de SÉLECTION : à la toute fin de la
    vidéo, la frame réellement montrée est celle de duree - 1/fps (bornage
    de temps_vignette), l'écart est d'une frame au plus.

    Args:
        video: Vidéo uploadée courante.
        debut: Borne basse de la sélection en secondes.
        fin: Borne haute de la sélection en secondes.
    """
    chemin = str(video.path)
    try:
        vignette_debut = extraire_vignette(
            chemin, video.file_id, temps_vignette(debut, video.duration, video.fps)
        )
        vignette_fin = extraire_vignette(
            chemin, video.file_id, temps_vignette(fin, video.duration, video.fps)
        )
    except (OSError, ValueError):
        # OSError : fichier illisible. ValueError : métadonnées aberrantes
        # (fps ou durée nuls d'un conteneur exotique). Dans les deux cas,
        # l'export échouera avec son propre message — pas de bandeau rouge
        # pour de simples vignettes.
        st.caption("Vignettes indisponibles pour cette vidéo.")
        return

    # Conteneur VERTICAL intermédiaire : st.columns n'expose que
    # vertical_alignment. En vertical, horizontal_alignment pilote l'axe
    # transversal du flex — image et légende restent empilées, mais centrées.
    # Nécessaire car st.image en width="content" garde sa largeur naturelle
    # (<= LARGEUR_MAX_EXTRACTION) et se calerait à gauche d'une demi-colonne.
    colonne_debut, colonne_fin = st.columns(2)
    with colonne_debut.container(horizontal_alignment="center"):
        st.image(vignette_debut, caption=f"Début · {debut:.1f} s")
    with colonne_fin.container(horizontal_alignment="center"):
        st.image(vignette_fin, caption=f"Fin · {fin:.1f} s")
