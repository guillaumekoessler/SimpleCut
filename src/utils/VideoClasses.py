from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class UploadedVideo:
    """Résultat d'un upload vidéo validé."""

    path: Path
    duration: float
