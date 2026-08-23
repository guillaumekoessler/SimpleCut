"""Palette globale unique d'un GIF : quelles images l'analysent, comment l'appliquer.

Pourquoi une palette GLOBALE et non une palette par image
---------------------------------------------------------
Le format autorise une table de couleurs locale par image, et c'est ce que fait
Pillow par défaut. Deux raisons de ne pas s'en contenter :

  - **le scintillement** : une palette recalculée par image ne retient pas
    exactement les mêmes 256 couleurs d'une image à l'autre, et l'ensemble pulse
    légèrement ;
  - **le delta inter-images** : Pillow ne réencode que le rectangle modifié
    d'une image à la suivante, mais deux images aux palettes différentes n'ont
    aucun index en commun, donc le rectangle vaut toujours l'image entière.

Une palette unique supprime les deux d'un coup — et rend `disposal=2` inutile
(cf. utils.GifExport), puisque les palettes ne diffèrent plus jamais.

Pourquoi AUCUN tramage
----------------------
LZW, seule compression du format, ne compresse que des suites de pixels d'index
identiques. Le tramage les détruit toutes. Mesuré sur une image d'aplat, taux de
transitions entre pixels horizontalement voisins :

    convert("P") — palette WEB + Floyd-Steinberg par défaut : 91,6 %
    quantification sur palette adaptative, sans tramage       :  1,1 %

Le même GIF passait de 2,14 Mo à 0,04 Mo, avec un écart de couleur qui tombait
de 16,9 à 1,1 sur 255. Le tramage coûtait donc doublement : le poids ET la
couleur. `dither=NONE` est écrit explicitement partout dans ce module : c'est la
valeur dont dépend tout le gain, elle ne doit pas pouvoir se perdre dans un
défaut de bibliothèque.

Couche pure : PIL uniquement, ni Streamlit ni MoviePy — même contrat que
utils.Layout et utils.PreviewGif.
"""

from __future__ import annotations

from collections.abc import Sequence

from PIL import Image

from utils.MathsVerif import _valider_positive_finite

# Un GIF n'adresse que 256 couleurs par image : c'est le format qui l'impose.
# On descent à 128 pour réduire la taille du fichier, et c'est suffisant pour un GIF animé
COULEURS_GIF = 128

# Nombre d'images qui servent à construire la palette. Mesuré : passer de 8 à
# 50 images ne bouge pas l'écart de couleur d'un centième. Le reliquat n'est pas
# un défaut d'échantillonnage mais une limite structurelle — chaque image prise
# isolément tient sous 256 couleurs, leur union sur tout le segment non.
IMAGES_ANALYSE = 16

# Largeur maximale des images d'analyse.
# A 240 px le GIF proche de la source.
# Le montage n'a pas à être fidèle, il doit être REPRÉSENTATIF
LARGEUR_ANALYSE = 240

# Filtre de réduction des images d'analyse. NEAREST prélève des pixels sans en
# calculer aucun — cf. _reduire, où le raisonnement est détaillé. Une seule
# source de vérité : construire_palette recadre au besoin et doit employer le
# même filtre, pour la même raison.
_FILTRE_ANALYSE = Image.Resampling.NEAREST

# Affinage par k-moyennes de la palette.
#
# Sans lui, une palette construite par découpe de l'espace des couleurs retient
# la MOYENNE de chaque cellule. Une moyenne est tirée vers le centre : les
# couleurs les plus saturées, les noirs les plus profonds et les blancs les plus
# francs n'ont aucune entrée qui les atteigne. Le GIF paraît alors terne sans
# qu'aucun écart de couleur ne soit grand — c'est un rétrécissement du gamut,
# pas une erreur ponctuelle, et l'écart absolu moyen ne le voit pas.
#
# Mesuré sur une vidéo de vigne, saturation moyenne rapportée à la source :
#
#     kmeans=0 : -2,8 %  (palette bornée à [6, 250] quand la source va de 0 à 255)
#     kmeans=1 : -0,5 %  (et l'écart de couleur baisse aussi, de 3,27 à 2,89)
#
# Au-delà de 1, Pillow ne bouge plus : c'est un interrupteur, pas un compteur
# d'itérations. Le coût est réel — 0,16 s à 1,25 s sur cette vidéo — et assumé.
KMEANS_AFFINAGE = 1


def instants_analyse(duree: float, fps: int, nb: int = IMAGES_ANALYSE) -> list[float]:
    """Instants auxquels prélever les images qui construiront la palette.

    Uniformément répartis sur toute la durée, JAMAIS les *n* premières images :
    une palette calée sur le début du plan trahirait tout changement de lumière
    ou de cadrage survenant plus loin.

    Les instants tombent au milieu de leur tranche plutôt qu'aux extrémités.
    Conséquence utile : `nb == 1` rend naturellement l'image du milieu, la plus
    représentative, sans cas particulier.

    Args:
        duree: Durée du segment en secondes (> 0, finie).
        fps: Cadence de sortie en images/s (> 0). Fixe la grille d'images sur
            laquelle les instants sont alignés.
        nb: Nombre d'instants souhaité (>= 1). Le résultat peut en compter
            MOINS : un segment plus court que `nb` images ne peut pas fournir
            deux fois la même sans travail inutile.

    Returns:
        Liste croissante et sans doublon d'instants dans [0, duree - 1/fps],
        jamais vide.

    Raises:
        ValueError: Si duree, fps ou nb est hors domaine, ou si le segment est
            trop court pour contenir ne serait-ce qu'une image.
    """
    _valider_positive_finite("duree", duree)
    _valider_positive_finite("fps", fps)
    if nb < 1:
        raise ValueError(f"nb doit être >= 1, reçu : {nb!r}")

    # Même arithmétique que utils.GifExport : un compte exact, pas une
    # estimation. Les instants tombent donc sur des images que la passe de
    # quantification produira réellement.
    total = int(duree * fps)
    if total < 1:
        raise ValueError(
            f"Segment trop court : {duree:.2f} s à {fps} i/s ne contient "
            f"aucune image."
        )

    # Demander une image exactement à t == duree fait lire ffmpeg au-delà de la
    # dernière : même doctrine que PreviewGif.temps_vignette.
    plafond = duree - 1.0 / fps

    indices = sorted({min(total - 1, int((i + 0.5) * total / nb)) for i in range(nb)})
    return [min(indice / fps, plafond) for indice in indices]


def construire_palette(echantillon: Sequence[Image.Image]) -> Image.Image:
    """Palette unique de 256 couleurs, déduite d'un échantillon d'images.

    Les images sont empilées en un montage vertical puis quantifiées d'un seul
    bloc : c'est ce qui garantit UNE palette pour tout le GIF et non une par
    image.

    MAXCOVERAGE répartit ses entrées pour COUVRIR l'espace des couleurs, là où
    MEDIANCUT les concentre là où les pixels sont denses. Conséquence directe
    sur le poids : les entrées étant plus écartées, davantage de pixels voisins
    tombent sur la même, ce qui allonge les suites d'index identiques — la seule
    chose que LZW sache compresser.

        vidéo de vigne : 10,59 Mo -> 9,53 Mo   (écart 2,89 -> 3,10)
        mire bruitée   :  5,49 Mo -> 3,85 Mo   (écart 1,25 -> 1,48)
        dégradé continu:  3,38 Mo -> 3,35 Mo   (écart 0,99 -> 0,88, meilleur)
        aplats         :  identique

    FASTOCTREE reste écarté : plus léger encore, mais il n'alloue que ~109
    couleurs sur 256 sur un dégradé continu et y produit des bandes visibles.

    L'affinage par k-moyennes n'est PAS optionnel (cf. KMEANS_AFFINAGE) : sans
    lui MAXCOVERAGE descend à 6,67 Mo mais tache les zones texturées et pose une
    dominante colorée sur les surfaces neutres.

    Args:
        echantillon: Images RGB, non vide. Réduites ici à LARGEUR_ANALYSE ;
            l'appelant n'a pas à s'en charger, le plafond mémoire appartient à
            ce module.

    Returns:
        Une image en mode « P » dont seule la palette sera utilisée.

    Raises:
        ValueError: Si l'échantillon est vide.
    """
    if not echantillon:
        raise ValueError("echantillon ne doit pas être vide")

    reduites = [_reduire(image) for image in echantillon]

    # Toutes les images d'un même segment ont la même taille ; on cale malgré
    # tout le montage sur la première, pour qu'une source hétérogène ne fasse
    # pas silencieusement déborder le collage.
    largeur, hauteur = reduites[0].size
    montage = Image.new("RGB", (largeur, hauteur * len(reduites)))
    for rang, image in enumerate(reduites):
        if image.size != (largeur, hauteur):
            image = image.resize((largeur, hauteur), _FILTRE_ANALYSE)
        montage.paste(image, (0, hauteur * rang))

    return montage.quantize(
        colors=COULEURS_GIF,
        method=Image.Quantize.MAXCOVERAGE,
        kmeans=KMEANS_AFFINAGE,
    )


def appliquer_palette(image: Image.Image, palette: Image.Image) -> Image.Image:
    """Réduit une image à la palette donnée, sans tramage.

    Args:
        image: Image RGB à quantifier.
        palette: Ce que rend construire_palette.

    Returns:
        Une image en mode « P », partageant la palette de toutes les autres —
        c'est cette identité de palette qui rend le delta inter-images possible
        à l'écriture.
    """
    return image.quantize(palette=palette, dither=Image.Dither.NONE)


def _reduire(image: Image.Image) -> Image.Image:
    """Ramène une image sous LARGEUR_ANALYSE, en préservant son ratio.

    NEAREST, et c'est le seul filtre acceptable ici : il PRÉLÈVE des pixels
    sans en calculer aucun. Chaque couleur du montage d'analyse est donc une
    couleur qui existe réellement dans la source.

    Tout filtre qui moyenne — BOX, BILINEAR, LANCZOS — rétrécit l'enveloppe des
    couleurs avant même que la palette ne soit calculée : moyenner un pixel
    saturé avec son voisin plus terne produit un pixel intermédiaire, et
    l'extrême disparaît de l'échantillon. Mesuré en BOX sur une vidéo de vigne :
    0,7 point de saturation perdu, en plus de celui que coûtait déjà la coupe
    médiane. Le raisonnement inverse — « la moyenne reste dans l'enveloppe des
    couleurs présentes » — est faux : elle y reste, mais elle la rétracte.

    Contrepartie assumée : le sous-échantillonnage peut manquer une couleur rare
    n'occupant que quelques pixels. Sur une palette de 256 entrées destinée à
    tout un segment, une teinte aussi marginale n'aurait de toute façon pas
    obtenu d'entrée.
    """
    if image.width <= LARGEUR_ANALYSE:
        return image

    hauteur = max(1, round(image.height * LARGEUR_ANALYSE / image.width))
    return image.resize((LARGEUR_ANALYSE, hauteur), _FILTRE_ANALYSE)
