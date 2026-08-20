"""Panneau de création du GIF : bouton, progression, aperçu, téléchargement."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import streamlit as st

from components.MediaLayout import colonne_image
from utils.GifClasses import ConversionParams, GifGenere
from utils.GifExport import convertir_en_gif, nom_fichier_gif
from utils.GifStore import CacheGifs, CleGif
from utils.VideoClasses import UploadedVideo

# Clé de session portant le cache des GIFs produits.
CLE_CACHE = "cache_gifs"

# Au-delà de ce volume de pixels à quantifier, on prévient. L'export garde
# toutes les images en mémoire (1 octet par pixel en mode palette) : 200 Mpx,
# c'est ~200 Mo de pic, soit 5 s de 1080p à 20 i/s.
SEUIL_ALERTE_PIXELS = 200_000_000


@st.fragment
def panneau_gif(video: UploadedVideo, params: ConversionParams | None) -> None:
    """Zone « créer le GIF » : bouton, génération, aperçu et téléchargement.

    Le point de conception : **l'affichage est une fonction de (identité
    courante, cache)**, pas une conséquence du clic. L'identité d'un GIF, c'est
    le couple (file_id de la vidéo, paramètres). Il en découle tout le
    comportement attendu, sans un seul drapeau d'état :

      - un rerun qui ne change rien réaffiche le GIF (il n'était rendu qu'une
        fois, dans la foulée du clic — c'était le bug) ;
      - bouger un réglage change l'identité, donc masque l'aperçu ;
      - revenir aux réglages précédents restitue le GIF depuis le cache, sans
        regénération ni même un clic à redonner.

    `@st.fragment` : sans lui, cliquer « Télécharger » relance TOUT le script,
    ce qui remonte le nœud <video> de l'aperçu et redémarre la lecture. Le
    fragment enferme les reruns de cette zone.

    Args:
        video: Vidéo courante.
        params: Paramètres du GIF, ou None si la sélection n'est pas
            exploitable (segment vide) — le panneau explique alors quoi faire.
    """
    cache = _cache_de_session()
    # Changer de vidéo doit emporter les GIFs de la précédente : plus rien ne
    # générera pour leur file_id, donc plus rien ne les évincerait.
    cache.purger_sauf(video.file_id)

    if params is None:
        st.info("Élargissez l'intervalle pour créer un GIF.")
        return

    cle: CleGif = (video.file_id, params)
    gif = cache.obtenir(cle)

    # st.empty et non st.container : c'est le seul conteneur qu'on puisse
    # VIDER. Sans ça, le run qui produit le GIF afficherait le bouton (rendu
    # avant que le GIF n'existe) ET l'aperçu, puis le bouton disparaîtrait au
    # rerun suivant — un clignotement pour rien.
    zone_bouton = st.empty()

    if gif is None:
        with zone_bouton.container(horizontal=True, horizontal_alignment="center"):
            demande = st.button(
                "Créer le GIF", type="primary", icon=":material/gif_box:"
            )
        if demande:
            gif = _generer(video, params, cache, cle)
            if gif is not None:
                zone_bouton.empty()

    if gif is not None:
        _afficher(video, gif)


def _cache_de_session() -> CacheGifs:
    """Le cache de la session courante, créé au premier passage."""
    if CLE_CACHE not in st.session_state:
        st.session_state[CLE_CACHE] = CacheGifs()
    return st.session_state[CLE_CACHE]


def _generer(
    video: UploadedVideo,
    params: ConversionParams,
    cache: CacheGifs,
    cle: CleGif,
) -> GifGenere | None:
    """Produit le GIF en montrant l'avancement, et le range dans le cache.

    Pas de callback ni de clé « demande en attente » en session : les valeurs
    des widgets du run courant sont déjà figées quand le script s'exécute, donc
    `if st.button(...)` suffit. C'est un aller-retour de moins à suivre.
    """
    _alerter_si_lourd(video, params)

    # mkstemp + close : le GIF est écrit par son chemin, on ne garde aucun
    # descripteur ouvert pendant l'écriture.
    # prefix : Streamlit n'offre aucun crochet de fin de session, donc les
    # derniers GIFs d'une session fermée survivent dans le dossier temporaire.
    # Le préfixe les rend au moins identifiables (et balayables un jour).
    descripteur, brut = tempfile.mkstemp(prefix="simplecut-gif-", suffix=".gif")
    os.close(descripteur)
    sortie = Path(brut)

    # expanded=True : le statut s'ouvre AVEC son contenu. Replié et vide, c'est
    # un tiroir qui ne contient rien — c'est exactement ce qu'il faisait avant.
    with st.status("Génération du GIF…", expanded=True) as statut:
        barre = st.progress(0.0, text="Lecture de la vidéo…")

        def rapporter(index: int, total: int) -> None:
            if index >= total:
                # Le décodage et la quantification sont finis ; il reste
                # l'assemblage du fichier, que Pillow fait d'un bloc (environ
                # un tiers du temps). Le nommer vaut mieux que laisser la barre
                # pleine devant une application qui semble figée.
                barre.progress(1.0, text="Assemblage du GIF…")
            else:
                barre.progress(index / total, text=f"Image {index} sur {total}")

        try:
            gif = convertir_en_gif(video.path, sortie, params, rapporter=rapporter)
        except Exception as erreur:
            # Volontairement large : au-delà d'OSError (fichier illisible) et
            # de ValueError (bornes ou segment impossibles), un conteneur
            # exotique peut faire lever MoviePy autrement, et une source
            # énorme peut lever MemoryError. Aucune de ces situations ne
            # justifie de peindre la page en rouge — ce qui emporterait aussi
            # l'aperçu vidéo et les vignettes. Sans risque pour les reruns :
            # les exceptions de contrôle de Streamlit héritent de
            # BaseException, pas d'Exception.
            # convertir_en_gif a déjà effacé son fichier de sortie.
            statut.update(label=f"Échec de la génération : {erreur}", state="error")
            return None

        statut.update(label="GIF prêt", state="complete", expanded=False)

    cache.deposer(cle, gif)
    return gif


def _alerter_si_lourd(video: UploadedVideo, params: ConversionParams) -> None:
    """Prévient avant un export qui va peser lourd en mémoire.

    Toutes les images sont quantifiées avant d'être assemblées : le pic mémoire
    grandit avec largeur × hauteur × nombre d'images. Mieux vaut le dire avant
    plutôt que de laisser l'onglet ramer.
    """
    largeur = video.width * params.resize_factor
    hauteur = video.height * params.resize_factor
    pixels = largeur * hauteur * params.duration * params.fps

    if pixels > SEUIL_ALERTE_PIXELS:
        st.warning(
            "Export volumineux : réduisez l'échelle ou l'intervalle si la "
            "génération traîne.",
            icon=":material/memory:",
        )


def _afficher(video: UploadedVideo, gif: GifGenere) -> None:
    """Aperçu centré, bouton de téléchargement centré, et le compte rendu."""
    try:
        # Une seule lecture disque, servie à la fois à l'aperçu et au
        # téléchargement.
        octets = gif.chemin.read_bytes()
    except OSError:
        # Course improbable mais possible : le fichier existait quand le cache
        # l'a validé, plus maintenant.
        st.caption("Aperçu indisponible : le fichier temporaire a disparu.")
        return

    # colonne_image et non colonne_media : le calage est le même, mais la règle
    # CSS de colonne_media vise les <video> et, étant globale, écraserait le
    # ratio de l'aperçu vidéo par celui du GIF.
    # Dimensions du GIF LUI-MÊME : la page passait ici celles de la source, ce
    # qui n'était juste que tant que le redimensionnement restait uniforme.
    with colonne_image(largeur=gif.largeur, hauteur=gif.hauteur):
        st.image(octets)

    with st.container(horizontal=True, horizontal_alignment="center"):
        st.download_button(
            "Télécharger le GIF",
            data=octets,
            file_name=nom_fichier_gif(video.name),
            mime="image/gif",
            icon=":material/download:",
        )

    st.caption(
        f"{gif.largeur} × {gif.hauteur} · {gif.nb_images} images · "
        f"{_taille_lisible(gif.taille_octets)}"
    )


def _taille_lisible(octets: int) -> str:
    """Taille de fichier en unité parlante — un GIF de 12 Mo doit se voir."""
    if octets < 1024:
        return f"{octets} o"
    if octets < 1024 * 1024:
        return f"{octets / 1024:.0f} Ko"
    return f"{octets / (1024 * 1024):.1f} Mo"
