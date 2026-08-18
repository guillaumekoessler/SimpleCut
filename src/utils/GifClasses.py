from dataclasses import dataclass
from pathlib import Path


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
        resize_factor: Facteur de redimensionnement (1.0 = taille originale).
    """

    start_time: float
    end_time: float
    fps: int = 10
    resize_factor: float = 1.0

    def __post_init__(self) -> None:
        # Arrondi AVANT validation. Ces paramètres servent de CLÉ d'identité au
        # GIF produit et arrivent de sliders, dont les valeurs portent du bruit
        # binaire (0.1 * 3 == 0.30000000000000004). Deux positions visuellement
        # identiques doivent donner la même clé — c'est la doctrine déjà
        # appliquée par temps_vignette dans utils.PreviewGif.
        object.__setattr__(self, "start_time", round(self.start_time, 6))
        object.__setattr__(self, "end_time", round(self.end_time, 6))
        object.__setattr__(self, "resize_factor", round(self.resize_factor, 6))

        if self.start_time < 0:
            raise ValueError("start_time doit être >= 0")
        if self.end_time <= self.start_time:
            raise ValueError("end_time doit être > start_time")
        if not 1 <= self.fps <= 60:
            raise ValueError("fps doit être entre 1 et 60")
        if not 0.1 <= self.resize_factor <= 1.0:
            raise ValueError("resize_factor doit être entre 0.1 et 1.0")

    @property
    def duration(self) -> float:
        """Durée du segment en secondes."""
        return self.end_time - self.start_time


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
