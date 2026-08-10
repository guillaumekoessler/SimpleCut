# tests/conftest.py
"""Fixtures partagées de la suite de tests."""

import sys
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest
from streamlit.testing.v1 import AppTest

RACINE = Path(__file__).parent.parent

# Miroir de App.py : on insère src/ sur le sys.path pour importer
# components/ et utils/ comme des packages de premier niveau.
sys.path.insert(0, str(RACINE / "src"))

# Importé APRÈS l'insertion du path, comme dans App.py.
from utils.VideoClasses import UploadedVideo  # noqa: E402

# st.video ne décode rien : il lit les octets du fichier et les transmet au
# navigateur. Un fichier bidon suffit donc à rendre un aperçu.
OCTETS_BIDON = b"\x00" * 16


# ---------------------------------------------------------------------------
# Fausses données
# ---------------------------------------------------------------------------
@pytest.fixture
def fabrique_video(tmp_path):
    """Fabrique un UploadedVideo adossé à un fichier bidon sur disque.

    UploadedVideo est frozen/slots : ses 9 champs sont tous requis. On les
    remplit ici une fois pour toutes ; chaque test ne surcharge que ce qu'il
    éprouve vraiment — le ratio pour le calage de l'aperçu, le nom et la durée
    pour la bannière de statut.
    """

    def _fabriquer(
        largeur: int = 640,
        hauteur: int = 360,
        *,
        nom: str = "fausse.mov",
        duree: float = 10.0,
    ) -> UploadedVideo:
        chemin = tmp_path / nom
        chemin.write_bytes(OCTETS_BIDON)
        return UploadedVideo(
            path=chemin,
            name=nom,
            duration=duree,
            width=largeur,
            height=hauteur,
            fps=30.0,
            size_bytes=len(OCTETS_BIDON),
            file_id="test-file-id",
            # Frame RGB minimale : de quoi rendre st.image sans décoder de vidéo.
            thumbnail=np.zeros((10, 10, 3), dtype=np.uint8),
        )

    return _fabriquer


# ---------------------------------------------------------------------------
# Rendu headless
# ---------------------------------------------------------------------------
def _lancer(at: AppTest, etat: dict) -> AppTest:
    """Amorce le session_state PUIS exécute : l'état doit précéder le run."""
    for cle, valeur in etat.items():
        at.session_state[cle] = valeur
    at.run()
    return at


@pytest.fixture
def rendre_app():
    """Rend un mini-app local (AppTest.from_function) avec un état initial.

        at = rendre_app(_app, dimensions=(640, 360))

    On ne vérifie PAS l'absence d'exception ici : certains tests attendent
    justement qu'une ValueError remonte. C'est à chaque test de l'affirmer.
    """

    def _rendre(app: Callable[[], None], **etat) -> AppTest:
        return _lancer(AppTest.from_function(app), etat)

    return _rendre


@pytest.fixture
def rendre_page():
    """Rend une vraie page de src/pages/ avec un état initial.

        at = rendre_page("src/pages/Home.py", uploaded_video=video)
    """

    def _rendre(page: str, **etat) -> AppTest:
        return _lancer(AppTest.from_file(str(RACINE / page)), etat)

    return _rendre


@pytest.fixture
def poids_apercu():
    """Renvoie les 3 poids de colonnes de l'aperçu média d'un AppTest rendu.

    On n'indexe PAS en aveugle : une page rend d'autres colonnes (la bannière de
    statut en sidebar, par exemple) et leur nombre changera. L'invariant robuste
    est structurel : l'aperçu est la seule colonne non vide encadrée par deux
    colonnes vides.
    """

    def _poids(at: AppTest) -> list[float]:
        cols = at.get("column")
        enfants = [len(c.children) for c in cols]
        milieux = [
            i
            for i in range(1, len(cols) - 1)
            if enfants[i - 1] == 0 and enfants[i] > 0 and enfants[i + 1] == 0
        ]
        assert len(milieux) == 1, f"triplet non identifiable : {enfants}"
        i = milieux[0]
        return [cols[j].proto.weight for j in (i - 1, i, i + 1)]

    return _poids
