from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


@dataclass(frozen=True, slots=True)
class UploadedVideo:
    """Résultat d'un upload vidéo validé."""

    path: Path
    name: str
    duration: float
    width: int
    height: int
    fps: float
    size_bytes: int
    file_id: str
    # le compare = False sert ici à ne pas forcer la comparaison des dataclasses constamment car un ndarray n'est pas comparable en ==
    thumbnail: np.ndarray = field(compare=False)
