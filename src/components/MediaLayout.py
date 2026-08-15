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

    Effet de bord assumé : émet une règle CSS GLOBALE au document qui fige le
    ratio de tout <video> de la page (cf. commentaire dans le corps). Sans elle,
    un rerun qui déplace les bornes de lecture fait sauter le scroll.

    Args:
        largeur: Largeur du média en pixels (> 0, finie).
        hauteur: Hauteur du média en pixels (> 0, finie).

    Returns:
        La colonne centrale, à utiliser comme gestionnaire de contexte.

    Raises:
        ValueError: dimensions invalides (propagée depuis utils.Layout).
    """
    # Les poids sont calculés EN PREMIER, avant toute émission : c'est
    # poids_colonnes_media qui valide les dimensions. Rien n'atteint donc le
    # DOM si elles sont invalides.
    poids = poids_colonnes_media(largeur, hauteur)

    # RÉSERVATION DE HAUTEUR DE L'APERÇU VIDÉO.
    #
    # Streamlit stylise <video> en `width:100%` SANS height ni aspect-ratio, et
    # il REMPLACE le nœud <video> dès que start_time/end_time changent (avec
    # autoplay=True, l'id de l'élément est calculé à partir de ces bornes).
    # Ici les bornes viennent de PreviewGif.bornes_boucle_video : elles bougent
    # à chaque seconde entière franchie. Le nœud neuf n'a pas encore ses
    # métadonnées et retombe à la hauteur par défaut d'un élément remplacé,
    # 150 px : la page raccourcit, le navigateur clampe le scroll, et
    # l'utilisateur est téléporté vers le haut. Mesuré sur une 480x854 : saut
    # de 368 px -> 0 px avec cette règle.
    #
    # Ce remontage est INTRINSÈQUE (la boucle doit suivre la sélection, donc
    # les bornes doivent changer) : cette règle n'est pas un pansement à
    # retirer un jour.
    #
    # Portée : GLOBALE au document. st.html n'ayant que des <style> part dans
    # le conteneur d'événements (elements/html.py:138-141), l'endroit de
    # l'appel n'y change rien — et le coût en espace est nul par construction.
    # Corollaire : si deux colonne_media de ratios DIFFÉRENTS coexistent un
    # jour, la dernière règle émise gagne (même spécificité).
    #
    # Le qualificateur `video` exclut la branche <iframe> YouTube de st.video,
    # qui porte le même data-testid et son propre aspect-ratio 16/9.
    #
    # float() garantit qu'un nombre — et rien d'autre — atteint la CSS :
    # _valider_positive_finite ne contraint que isfinite() et le signe, pas la
    # représentation textuelle.
    st.html(
        f'<style>video[data-testid="stVideo"]'
        f"{{aspect-ratio:{float(largeur)} / {float(hauteur)};"
        f"object-fit:contain}}</style>"
    )

    # gap="small" (défaut) : les constantes de calage ont été mesurées avec CE gap.
    # Le rendre paramétrable invaliderait le calage — on le fige volontairement.
    _, milieu, _ = st.columns(poids)
    return milieu
