from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class ConversionParams:
    """Paramètres pour la conversion d'une vidéo en GIF.

    Attributes:
        start_time: Temps de début en secondes.
        end_time: Temps de fin en secondes.
        fps: Images par seconde du GIF de sortie (10-20 recommandé).
        resize_factor: Facteur de redimensionnement (1.0 = taille originale).
    """

    start_time: float
    end_time: float
    fps: int = 15
    resize_factor: float = 1.0

    def __post_init__(self) -> None:
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
