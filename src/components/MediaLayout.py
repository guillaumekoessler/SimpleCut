"""Mise en page centrée des aperçus média."""

from __future__ import annotations

from typing import TYPE_CHECKING

import streamlit as st

from utils.Layout import poids_colonnes_media

if TYPE_CHECKING:
    # Chemin semi-interne de Streamlit : utile pour l'annotation, jamais importé
    # au runtime pour ne pas dépendre de sa stabilité.
    from streamlit.delta_generator import DeltaGenerator


def colonne_media(largeur: float, hauteur: float) -> DeltaGenerator:
    """Colonne centrale dimensionnée pour un média de ce ratio.

    À utiliser en `with` pour TOUT aperçu média centré :

        with colonne_media(largeur=video.width, hauteur=video.height):
            st.video(chemin)          # remplit toujours sa colonne
            st.image(octets)          # "content" : la colonne sert de PLAFOND

    Note: st.video n'accepte pas width="content" — il remplit sa colonne.
          st.image en "content" (défaut) n'est que plafonné par elle.

    Args:
        largeur: Largeur du média en pixels (> 0, finie).
        hauteur: Hauteur du média en pixels (> 0, finie).

    Returns:
        La colonne centrale, à utiliser comme gestionnaire de contexte.

    Raises:
        ValueError: dimensions invalides (propagée depuis utils.Layout).
    """
    # gap="small" (défaut) : les constantes de calage ont été mesurées avec CE gap.
    # Le rendre paramétrable invaliderait le calage — on le fige volontairement.
    _, milieu, _ = st.columns(poids_colonnes_media(largeur, hauteur))
    return milieu
