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

Pourquoi l'export fait DEUX passes sur la vidéo
-----------------------------------------------
La palette est globale (cf. utils.GifPalette), donc il faut l'avoir construite
avant de quantifier la première image. Une passe d'analyse la précède donc.

Elle ne décode pas le segment en entier : elle prélève 16 images par `get_frame`
à des instants calculés. Le décodage linéaire aurait suivi la longueur du
segment, les seeks non — c'est le point, plus que le gain brut :

    50 images  : linéaire 0,37 s | 16 seeks 0,21 s
    100 images : linéaire 0,62 s | 16 seeks 0,21 s

Sur un segment de 30 s à 20 i/s le linéaire coûterait ~4 s, les seeks toujours
0,2 à 0,3 s.

Ce découpage préserve aussi le pic mémoire : analyser impose des images RGB à
3 octets par pixel, mais seules 16 sont retenues, et plafonnées en largeur par
utils.GifPalette. La passe de quantification, elle, reste en flux.

Couche MoviePy/Pillow : ce module décode et écrit des pixels, mais ne connaît
ni Streamlit ni la notion de session — il s'éprouve donc sans AppTest.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from enum import StrEnum
from pathlib import Path

from moviepy import VideoFileClip
from PIL import Image

from utils.GifClasses import ConversionParams, GifGenere
from utils.GifPalette import appliquer_palette, construire_palette, instants_analyse


class Phase(StrEnum):
    """Étape d'export en cours, telle qu'annoncée au rapporteur.

    L'export ne se déroule plus en un seul mouvement : nommer la phase permet à
    l'appelant de libeller sa progression au lieu d'afficher un compteur dont le
    total change en cours de route.
    """

    ANALYSE = "analyse"
    QUANTIFICATION = "quantification"
    ASSEMBLAGE = "assemblage"


# Le rapporteur reçoit (phase, index, total) après chaque unité de travail.
# Contrat : `1 <= index <= total` et `total >= 1`, dans chaque phase.
Rapporteur = Callable[[Phase, int, int], None]

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
    rapporter: Rapporteur | None = None,
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
        rapporter: Appelée après chaque unité de travail, avec
            (phase, index, total). Le total est propre à la phase : les images
            analysées ne se comptent pas avec les images quantifiées.
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

            # ConversionParams est SEUL à décider des dimensions : elles
            # combinent l'échelle demandée et le plafond du format, et le
            # panneau s'appuie sur le même calcul pour son alerte mémoire.
            cible = params.dimensions_sortie(clip.w, clip.h)
            if cible != (clip.w, clip.h):
                segment = segment.resized(cible)

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

            # L'analyse vient APRÈS le garde-fou ci-dessus : un segment
            # dégénéré doit échouer avant qu'on décode quoi que ce soit.
            palette = _analyser(segment, params.fps, rapporter)
            images = _quantifier(segment, params.fps, a_produire, palette, rapporter)
            largeur, hauteur = segment.size

        if rapporter is not None:
            # L'assemblage est fait d'un bloc par Pillow, sans crochet possible :
            # on ne peut pas le mesurer, seulement le nommer. Le taire laisserait
            # l'application paraître figée pendant environ un tiers du temps.
            rapporter(Phase.ASSEMBLAGE, 1, 1)

        # duration : délai d'affichage en millisecondes. params.fps divisant
        # 100, c'est un multiple de 10 — le seul cas où le GIF joue juste.
        # loop=0 : boucle infinie.
        #
        # Pas de disposal=2 : il demandait à chaque image d'effacer la
        # précédente, ce qui interdisait à Pillow de n'encoder que le rectangle
        # modifié (mesuré sur un fond fixe : 0,17 Mo contre 0,06 Mo). Il ne
        # servait qu'à éviter les traînées entre palettes différentes — or la
        # palette est désormais unique, donc les palettes ne diffèrent jamais.
        #
        # palette= est OBLIGATOIRE et n'est pas une redondance : sans lui,
        # _write_multiple_frames pose `include_color_table = True` sur chaque
        # image delta et réécrit une table de couleurs par image, sans voir
        # qu'elles partagent déjà la même. Mesuré : 49 tables locales écrites
        # pour rien, et 3 à 13 % du fichier selon le contenu, à couleur
        # rigoureusement identique.
        images[0].save(
            chemin_sortie,
            save_all=True,
            append_images=images[1:],
            duration=1000 // params.fps,
            loop=0,
            palette=palette.getpalette(),
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


def _analyser(segment, fps: int, rapporter: Rapporteur | None) -> Image.Image:
    """Construit la palette globale à partir d'images prélevées sur le segment.

    Seule cette passe manipule des images RGB, et elle n'en retient que 16 —
    utils.GifPalette les plafonne en largeur, de sorte que son pic mémoire est
    constant quelle que soit la résolution de la source.
    """
    instants = instants_analyse(segment.duration, fps)
    echantillon: list[Image.Image] = []

    for index, instant in enumerate(instants, start=1):
        echantillon.append(Image.fromarray(segment.get_frame(instant)))
        if rapporter is not None:
            rapporter(Phase.ANALYSE, index, len(instants))

    return construire_palette(echantillon)


def _quantifier(
    segment,
    fps: int,
    total: int,
    palette: Image.Image,
    rapporter: Rapporteur | None,
) -> list[Image.Image]:
    """Décode chaque image du segment et la réduit à la palette globale.

    C'est ici qu'est le gros du travail, donc ici que la progression a un sens
    (cf. l'en-tête du module). Toutes les images partagent la MÊME table de
    couleurs : c'est ce qui supprime le scintillement de palette et ce qui rend
    exploitable le delta inter-images à l'écriture.

    En flux, une image à la fois : ce qui s'accumule est en mode « P », à
    1 octet par pixel.
    """
    images: list[Image.Image] = []

    for index, frame in enumerate(
        segment.iter_frames(fps=fps, dtype="uint8", logger=None), start=1
    ):
        images.append(appliquer_palette(Image.fromarray(frame), palette))
        if rapporter is not None:
            rapporter(Phase.QUANTIFICATION, index, total)

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
