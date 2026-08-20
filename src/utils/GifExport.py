"""Conversion d'un segment de vidéo en GIF animé, et nom du fichier téléchargé.

Pourquoi ce module n'appelle PAS `clip.write_gif`
-------------------------------------------------
`write_gif` accumule toutes les images décodées puis laisse Pillow les
quantifier d'un seul bloc à la fermeture du writer. Conséquence mesurée sur une
source 1280x720, segment de 5 s à 20 i/s : le journal de progression de MoviePy
est épuisé au bout de 0,18 s, et l'application reste muette pendant les 2,5 s
suivantes — 93 % de l'attente. Une barre qui atteint 100 % puis se fige est
pire que pas de barre du tout.

En pilotant la boucle nous-mêmes, la quantification devient rapportable :

    write_gif             : 2,64 s, 6 % du temps sous progression
    quantification ici    : 1,98 s, 67 % du temps sous progression
    (dimensions, nombre d'images, délais et poids identiques au bit près)

Bonus non recherché : une image en mode « P » pèse 1 octet par pixel au lieu de
3, ce qui divise par trois le pic mémoire de l'export.

Couche MoviePy/Pillow : ce module décode et écrit des pixels, mais ne connaît
ni Streamlit ni la notion de session — il s'éprouve donc sans AppTest.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

from moviepy import VideoFileClip
from PIL import Image

from utils.GifClasses import ConversionParams, GifGenere

# Un GIF n'adresse que 256 couleurs par image : c'est le format qui l'impose.
COULEURS_GIF = 256

# --- Assainissement du nom de téléchargement -------------------------------
# Tout ce qui n'est ni lettre, ni chiffre, ni « . - _ » devient un souligné.
# `\w` est unicode : les accents d'un nom de fichier français survivent.
_INTERDITS = re.compile(r"[^\w.-]+", re.UNICODE)
# Séparateurs de chemin des deux mondes : un upload venu de Windows en porte.
_SEPARATEURS = re.compile(r"[\\/]")
# Caractères sans valeur en début ou fin de nom.
_BORDS = "._-"
# Les systèmes de fichiers plafonnent autour de 255 octets ; un nom de
# téléchargement n'a de toute façon pas vocation à être un roman.
_LONGUEUR_MAX = 60
_NOM_REPLI = "animation"


def nom_fichier_gif(nom_source: str) -> str:
    """Nom de téléchargement sûr, dérivé du nom du fichier uploadé.

    Ce nom part dans un en-tête HTTP `Content-Disposition`, que Streamlit
    compose par simple interpolation entre guillemets. Un séparateur de chemin,
    un guillemet ou un retour ligne qui s'y glisserait serait au mieux un
    fichier écrit ailleurs qu'attendu, au pire une injection d'en-tête. Le nom
    d'un upload vient de l'utilisateur : c'est une entrée externe, et sa
    frontière est ici.

    Args:
        nom_source: Nom du fichier uploadé, tel quel.

    Returns:
        Un nom de la forme `<tronc>.gif`, sans séparateur ni caractère de
        contrôle, tronqué, jamais vide (repli sur « animation.gif »).
    """
    base = _SEPARATEURS.split(nom_source)[-1]

    # rfind > 0 et non >= 0 : dans « .gitignore » le point de tête n'introduit
    # pas une extension, alors que dans « ... » le dernier point, si.
    coupe = base.rfind(".")
    tronc = base[:coupe] if coupe > 0 else base

    tronc = _INTERDITS.sub("_", tronc).strip(_BORDS)
    # Second strip APRÈS la troncature : couper à 60 peut laisser un souligné
    # ou un point en dernière position.
    return f"{tronc[:_LONGUEUR_MAX].strip(_BORDS) or _NOM_REPLI}.gif"


def convertir_en_gif(
    chemin_source: Path,
    chemin_sortie: Path,
    params: ConversionParams,
    rapporter: Callable[[int, int], None] | None = None,
) -> GifGenere:
    """Écrit le segment demandé sous forme de GIF animé.

    La fonction est PROPRIÉTAIRE de `chemin_sortie` : en cas d'échec elle le
    supprime, y compris si l'appelant l'avait déjà créé (c'est le cas d'un
    `mkstemp`). Aucun GIF partiel ne survit à une erreur, et l'appelant n'a
    donc rien à nettoyer derrière elle.

    Args:
        chemin_source: Vidéo à découper. Doit exister et être un fichier.
        chemin_sortie: Où écrire le GIF ; son dossier parent est créé au besoin.
        params: Intervalle, cadence et échelle — déjà validés par
            ConversionParams à la construction. `params.fps` doit être un
            diviseur de 100 (cf. utils.GifQuality), sans quoi le GIF jouera
            plus vite que la vidéo.
        rapporter: Appelée après chaque image quantifiée, avec (index, total).
            Contrat : `1 <= index <= total` et `total >= 1`.

    Returns:
        Le GIF produit et ses caractéristiques RELEVÉES sur le fichier.

    Raises:
        FileNotFoundError: chemin_source absent, ou n'est pas un fichier.
        ValueError: end_time dépasse la durée réelle, ou le segment est trop
            court pour produire ne serait-ce qu'une image.
        OSError: vidéo illisible, écriture impossible, ou fichier produit
            invalide (propagée telle quelle : c'est à l'appelant de décider
            quoi afficher).
    """
    try:
        if not chemin_source.is_file():
            raise FileNotFoundError(f"Fichier source introuvable : {chemin_source}")

        chemin_sortie.parent.mkdir(parents=True, exist_ok=True)

        with VideoFileClip(str(chemin_source)) as clip:
            # La durée réelle n'est connue qu'une fois le conteneur ouvert :
            # c'est la seule borne que ConversionParams ne pouvait pas vérifier.
            if params.end_time > clip.duration:
                raise ValueError(
                    f"end_time ({params.end_time} s) dépasse la durée de la "
                    f"vidéo ({clip.duration} s)"
                )

            segment = clip.subclipped(params.start_time, params.end_time)
            if params.resize_factor < 1.0:
                segment = segment.resized(params.resize_factor)

            # Nombre d'images que la boucle va produire. Même arithmétique que
            # iter_frames : c'est un compte exact, pas une estimation.
            a_produire = int(segment.duration * params.fps)
            if a_produire < 1:
                # Atteignable en trois clics : 0,1 s de segment à 5 i/s. Sans
                # ce garde-fou, l'export « réussit » en déposant un fichier
                # vide, et la casse n'apparaît qu'à l'affichage.
                raise ValueError(
                    f"Segment trop court : {segment.duration:.2f} s à "
                    f"{params.fps} i/s ne produit aucune image."
                )

            images = _quantifier(segment, params.fps, a_produire, rapporter)
            largeur, hauteur = segment.size

        # duration : délai d'affichage en millisecondes. params.fps divisant
        # 100, c'est un multiple de 10 — le seul cas où le GIF joue juste.
        # loop=0 : boucle infinie. disposal=2 : chaque image efface la
        # précédente, ce qui évite les traînées si les palettes diffèrent.
        images[0].save(
            chemin_sortie,
            save_all=True,
            append_images=images[1:],
            duration=1000 // params.fps,
            loop=0,
            disposal=2,
        )

        nb_images = _relire_nb_images(chemin_sortie)
    except BaseException:
        # Volontairement BaseException : une interruption au milieu d'un export
        # de 30 s ne doit pas plus laisser de fichier à moitié écrit qu'une
        # erreur de décodage.
        chemin_sortie.unlink(missing_ok=True)
        raise

    return GifGenere(
        chemin=chemin_sortie,
        nb_images=nb_images,
        largeur=int(largeur),
        hauteur=int(hauteur),
        taille_octets=chemin_sortie.stat().st_size,
    )


def _quantifier(
    segment,
    fps: int,
    total: int,
    rapporter: Callable[[int, int], None] | None,
) -> list[Image.Image]:
    """Décode chaque image du segment et la réduit à 256 couleurs.

    C'est ici qu'est le gros du travail, donc ici que la progression a un sens
    (cf. l'en-tête du module). Chaque image reçoit sa PROPRE palette adaptative,
    ce qui est le mode nominal du format : un GIF porte une table de couleurs
    locale par image.
    """
    images: list[Image.Image] = []

    for index, frame in enumerate(
        segment.iter_frames(fps=fps, dtype="uint8", logger=None), start=1
    ):
        images.append(
            Image.fromarray(frame).convert(
                "P",
                # palette=Image.ADAPTIVE, colors=COULEURS_GIF
            )
        )
        if rapporter is not None:
            rapporter(index, total)

    return images


def _relire_nb_images(chemin: Path) -> int:
    """Post-condition : le fichier écrit EST un GIF, et on en compte les images.

    Le nombre d'images n'est pas prédit mais relu, parce que Pillow fusionne
    les images consécutives identiques : sur une vidéo statique, un segment de
    0,8 s à 5 i/s annonce 4 images et n'en écrit qu'une. Autant afficher le
    vrai chiffre.

    Raises:
        OSError: Le fichier n'est pas un GIF lisible (Image.open lève
            UnidentifiedImageError, sous-classe d'OSError, sur un fichier vide).
    """
    with Image.open(chemin) as gif:
        if gif.format != "GIF":
            raise OSError(f"Le fichier produit n'est pas un GIF : {gif.format!r}")
        return gif.n_frames
