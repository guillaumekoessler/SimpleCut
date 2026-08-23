from dataclasses import dataclass
from pathlib import Path

# Largeur maximale d'un GIF produit. Le format n'a aucune compression
# inter-pixels utile sur du contenu photographique : mesuré sur une vidéo de
# vigne, la carte d'index porte 7,89 bits d'entropie sur 8 possibles, et 82 %
# des pixels diffèrent de leur voisin. Le poids est donc quasi PROPORTIONNEL au
# nombre de pixels, et aucun réglage d'encodage n'y changera rien — ffmpeg, la
# référence du domaine, sort à 5 % de nous sur le même segment.
#
# Réduire les pixels est le seul levier qui ne coûte AUCUNE couleur : sur cette
# vidéo, l'écart colorimétrique reste à 2,89 de 640 px à 384 px, alors que
# réduire la palette le fait passer de 2,89 à 5,26. D'où un plafond plutôt
# qu'un réglage.
#
#     640 px : 10,59 Mo      480 px : 5,53 Mo      384 px : 3,56 Mo
#
# 480 px place le GIF au poids de l'ancienne implémentation (5,54 Mo) avec un
# écart de couleur 4,7 fois moindre (3,10 contre 14,58).
LARGEUR_MAX_GIF = 480

# En dessous, un GIF cesse d'être lisible avant d'être léger.
LARGEUR_MIN_GIF = 120

# Largeurs offertes à l'utilisateur. Des pixels et non un pourcentage : un
# pourcentage se lit différemment selon la source, et surtout il créait une zone
# morte — sur une source 1080p plafonnée à 480 px, le curseur ne faisait rien
# de 100 % à 25 %. Une largeur en pixels dit exactement ce qu'elle produit.
#
# Le poids suit le nombre de pixels de façon quasi linéaire (0,85 octet par
# pixel, constant à 5 % près sur toute la plage), donc diviser la largeur par
# deux divise le poids par QUATRE — la hauteur suit.
LARGEURS_PROPOSEES: tuple[int, ...] = (160, 240, 320, 400, 480)


@dataclass(frozen=True)
class ConversionParams:
    """Paramètres pour la conversion d'une vidéo en GIF.

    Frozen : ces paramètres servent de CLÉ d'identité au GIF produit
    (cf. utils.GifStore). Une instance mutable, ou non comparable, casserait
    la règle « l'aperçu ne disparaît que si l'identité change ».

    Attributes:
        start_time: Temps de début en secondes.
        end_time: Temps de fin en secondes.
        fps: Images par seconde du GIF de sortie. À choisir dans
            utils.GifQuality.FPS_EXACTS, sans quoi le GIF joue faux.
        largeur_cible: Largeur demandée pour le GIF, en pixels. Plafonnée à la
            largeur de la source par dimensions_sortie : on ne fabrique jamais
            des pixels que la vidéo n'a pas.
    """

    start_time: float
    end_time: float
    fps: int = 10
    largeur_cible: int = LARGEUR_MAX_GIF

    def __post_init__(self) -> None:
        # Arrondi AVANT validation. Ces paramètres servent de CLÉ d'identité au
        # GIF produit et arrivent de sliders, dont les valeurs portent du bruit
        # binaire (0.1 * 3 == 0.30000000000000004). Deux positions visuellement
        # identiques doivent donner la même clé — c'est la doctrine déjà
        # appliquée par temps_vignette dans utils.PreviewGif.
        object.__setattr__(self, "start_time", round(self.start_time, 6))
        object.__setattr__(self, "end_time", round(self.end_time, 6))

        if self.start_time < 0:
            raise ValueError("start_time doit être >= 0")
        if self.end_time <= self.start_time:
            raise ValueError("end_time doit être > start_time")
        if not 1 <= self.fps <= 60:
            raise ValueError("fps doit être entre 1 et 60")
        # Le plafond est vérifié ICI et pas seulement à l'affichage : c'est la
        # politique de sortie du produit, elle ne doit pas dépendre du fait que
        # l'appelant soit une page ou un script.
        if not 1 <= self.largeur_cible <= LARGEUR_MAX_GIF:
            raise ValueError(
                f"largeur_cible doit être entre 1 et {LARGEUR_MAX_GIF}, "
                f"reçu : {self.largeur_cible!r}"
            )

    @property
    def duration(self) -> float:
        """Durée du segment en secondes."""
        return self.end_time - self.start_time

    def dimensions_sortie(self, largeur: int, hauteur: int) -> tuple[int, int]:
        """Dimensions du GIF pour une source de cette taille.

        La largeur commande, la hauteur suit : le ratio de la source est
        toujours conservé.

        Source unique de vérité des dimensions de sortie — l'export s'en sert
        pour redimensionner, le panneau pour estimer le pic mémoire, la page
        pour annoncer la taille. Les faire diverger rendrait l'alerte fausse
        dès qu'une source est plus étroite que la largeur demandée.

        Args:
            largeur: Largeur de la vidéo source en pixels (>= 1).
            hauteur: Hauteur de la vidéo source en pixels (>= 1).

        Returns:
            (largeur, hauteur) en pixels, chacune >= 1 — une source minuscule
            ne doit jamais produire une dimension nulle, que MoviePy refuserait.

        Raises:
            ValueError: Si largeur ou hauteur est < 1.
        """
        if largeur < 1 or hauteur < 1:
            raise ValueError(f"dimensions source invalides : {largeur}x{hauteur}")

        # Jamais d'agrandissement : demander plus large que la source ne
        # produirait que du flou, pour un poids qui, lui, serait bien réel.
        cible_l = min(self.largeur_cible, largeur)
        return max(1, cible_l), max(1, round(hauteur * cible_l / largeur))


@dataclass(frozen=True, slots=True)
class GifGenere:
    """Un GIF écrit sur le disque, et ce qu'il faut pour le présenter.

    Les dimensions sont celles du GIF LUI-MÊME, relevées après
    redimensionnement — jamais recalculées depuis la source. C'est ce qui
    permet de caler l'aperçu sans supposer que l'échelle est restée uniforme,
    et ce qui restera juste le jour où un recadrage ou une rotation
    s'ajouteront au pipeline.

    Attributes:
        chemin: Fichier GIF. Temporaire : sa durée de vie est celle du cache
            qui le détient (cf. utils.GifStore).
        nb_images: Nombre d'images réellement écrites.
        largeur: Largeur du GIF en pixels.
        hauteur: Hauteur du GIF en pixels.
        taille_octets: Taille du fichier sur le disque.
    """

    chemin: Path
    nb_images: int
    largeur: int
    hauteur: int
    taille_octets: int


def largeurs_disponibles(largeur_source: int) -> tuple[int, ...]:
    """Largeurs de sortie proposables pour une source de cette largeur.

    Le catalogue est PLAFONNÉ par la source, exactement comme
    utils.GifQuality.vitesses_disponibles l'est par la cadence : proposer une
    largeur qu'on ne peut atteindre qu'en agrandissant ne donnerait que du flou
    et du poids. Mieux vaut ne pas l'offrir que de la laisser décevoir.

    La largeur maximale atteignable figure TOUJOURS dans le résultat, même
    lorsqu'elle ne fait pas partie de LARGEURS_PROPOSEES : une source de 300 px
    doit pouvoir sortir en 300 px, c'est-à-dire sans aucune réduction.

    Args:
        largeur_source: Largeur de la vidéo importée en pixels (>= 1).

    Returns:
        Tuple croissant, sans doublon, jamais vide.

    Raises:
        ValueError: Si largeur_source est < 1.
    """
    if largeur_source < 1:
        raise ValueError(f"largeur_source doit être >= 1, reçu : {largeur_source!r}")

    plafond = min(largeur_source, LARGEUR_MAX_GIF)
    valeurs = {
        offerte
        for offerte in LARGEURS_PROPOSEES
        if LARGEUR_MIN_GIF <= offerte <= plafond
    }
    valeurs.add(plafond)
    return tuple(sorted(valeurs))
