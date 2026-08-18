# tests/conftest.py
"""Fixtures partagées de la suite de tests."""

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from streamlit.testing.v1 import AppTest

from tests.donnees import ROUGE

RACINE = Path(__file__).parent.parent

# Miroir de App.py : on insère src/ sur le sys.path pour importer
# components/ et utils/ comme des packages de premier niveau.
sys.path.insert(0, str(RACINE / "src"))

# Importé APRÈS l'insertion du path, comme dans App.py.
from utils.VideoClasses import UploadedVideo  # noqa: E402

# Gabarit du clip de test : assez grand pour décoder, trop petit pour coûter.
TAILLE_CLIP = (64, 48)
FPS_CLIP = 10
DUREE_CLIP = 1.0


# ---------------------------------------------------------------------------
# Clips réels
# ---------------------------------------------------------------------------
def _ecrire_clip(chemin: Path, couleur: tuple[int, int, int] = ROUGE) -> Path:
    """Écrit un mp4 de couleur unie à l'emplacement demandé, et le renvoie."""
    # Import local : ne pas payer l'import MoviePy à chaque collecte pytest.
    from moviepy import ColorClip

    clip = ColorClip(size=TAILLE_CLIP, color=couleur, duration=DUREE_CLIP)
    clip.with_fps(FPS_CLIP).write_videofile(str(chemin), logger=None)
    return chemin


@pytest.fixture(scope="session")
def fabrique_clip() -> Callable[..., Path]:
    """Fabrique un clip mp4 réel : fabrique_clip(chemin, couleur=VERT).

    Pour les tests qui ont besoin d'un SECOND clip (autre couleur, chemin
    recyclé…). Le clip nominal, lui, est déjà servi par clip_reel.
    """
    return _ecrire_clip


@pytest.fixture(scope="session")
def clip_reel(tmp_path_factory) -> Path:
    """Petit clip mp4 RÉEL (64x48, 10 fps, 1 s), généré une fois par session.

    Nécessaire dès qu'un test décode vraiment des frames (extraction de
    vignettes) : le fichier bidon de fabrique_video ne suffit plus.
    Généré plutôt que commité : pas de binaire dans le dépôt.
    """
    return _ecrire_clip(tmp_path_factory.mktemp("clips") / "mini.mp4")


# ---------------------------------------------------------------------------
# Fausses données
# ---------------------------------------------------------------------------
@pytest.fixture
def fabrique_video(tmp_path) -> Callable[..., UploadedVideo]:
    """Fabrique un UploadedVideo.

    Par défaut il pointe sur un fichier bidon de 16 octets : st.video ne
    décode rien, il lit les octets et les transmet au navigateur. Aucune vraie
    vidéo n'est nécessaire pour rendre un aperçu — et ce fichier sert aussi à
    éprouver le chemin d'échec du décodage.

    Pour un fichier réellement décodable, passer `chemin=` (c'est ce que fait
    la fixture video_reelle) ou prendre directement video_reelle.

    UploadedVideo est frozen/slots : ses 9 champs sont tous requis. Ils ont
    tous une valeur par défaut ici ; n'en surcharger que ce que le test
    éprouve vraiment.
    """

    def _fabriquer(
        largeur: int = 640,
        hauteur: int = 360,
        *,
        chemin: Path | None = None,
        nom: str = "fausse.mov",
        duree: float = 10.0,
        fps: float = 30.0,
        file_id: str = "test-file-id",
    ) -> UploadedVideo:
        if chemin is None:
            chemin = tmp_path / nom
            chemin.write_bytes(b"\x00" * 16)

        return UploadedVideo(
            path=chemin,
            name=nom,
            duration=duree,
            width=largeur,
            height=hauteur,
            fps=fps,
            size_bytes=chemin.stat().st_size,
            file_id=file_id,
            # Frame RGB minimale : de quoi rendre st.image sans décoder de vidéo.
            thumbnail=np.zeros((10, 10, 3), dtype=np.uint8),
        )

    return _fabriquer


@pytest.fixture
def video_reelle(clip_reel, fabrique_video) -> UploadedVideo:
    """UploadedVideo adossé au clip réel — pour les tests qui décodent."""
    return fabrique_video(
        *TAILLE_CLIP,
        chemin=clip_reel,
        nom="mini.mp4",
        duree=DUREE_CLIP,
        fps=float(FPS_CLIP),
        file_id="clip-reel",
    )


# ---------------------------------------------------------------------------
# Isolation du cache
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _cache_vignettes_propre() -> None:
    """Vide le cache d'extraction de vignettes avant chaque test.

    extraire_vignette est un `st.cache_data` GLOBAL et clip_reel est
    session-scoped : sans ce nettoyage, une entrée posée par un test resservait
    au suivant (même chemin, même file_id) et l'ordre d'exécution devenait
    signifiant. N'invalide pas test_frames.py, qui n'éprouve que du cache
    intra-test.

    On lit sys.modules plutôt que d'importer : un test de couche pure
    (test_layout, test_preview_gif) ne doit pas se mettre à dépendre de
    MoviePy. Si le module n'est pas chargé, il n'y a rien à vider.
    """
    frames = sys.modules.get("utils.Frames")
    if frames is not None:
        frames.extraire_vignette.clear()


# ---------------------------------------------------------------------------
# Rendu headless
# ---------------------------------------------------------------------------
def _lancer(at: AppTest, etat: dict[str, Any], *, sans_erreur: bool) -> AppTest:
    """Amorce le session_state PUIS exécute : l'état doit précéder le run."""
    for cle, valeur in etat.items():
        at.session_state[cle] = valeur
    at.run()
    if sans_erreur:
        assert not at.exception, at.exception
    return at


@pytest.fixture
def rendre_app() -> Callable[..., AppTest]:
    """Rend un mini-app local (AppTest.from_function) avec un état initial.

        at = rendre_app(_app, dimensions=(640, 360))
        at = rendre_app(_app, args=(video, 0.0, 0.9))

    `args` / `kwargs` sont transmis à la fonction-script : c'est le seul moyen
    de lui passer un objet, AppTest ré-exécutant son CODE SOURCE comme un
    script isolé (d'où aussi l'obligation d'importer dans le corps — aucune
    fermeture ne survit).

    `sans_erreur=True` par défaut : c'est le cas de la quasi-totalité des
    tests. Ceux qui ATTENDENT une exception passent False et l'affirment
    eux-mêmes. Conséquence : `args`, `kwargs` et `sans_erreur` sont des noms
    réservés, ils ne peuvent pas servir de clé de session_state.
    """

    def _rendre(
        app: Callable[..., None],
        *,
        args: tuple[Any, ...] | None = None,
        kwargs: dict[str, Any] | None = None,
        sans_erreur: bool = True,
        **etat: Any,
    ) -> AppTest:
        return _lancer(
            AppTest.from_function(app, args=args, kwargs=kwargs),
            etat,
            sans_erreur=sans_erreur,
        )

    return _rendre


@pytest.fixture
def rendre_page() -> Callable[..., AppTest]:
    """Rend une vraie page de src/pages/ avec un état initial.

    at = rendre_page("src/pages/Home.py", uploaded_video=video)

    Même contrat que rendre_app pour `sans_erreur`.
    """

    def _rendre(page: str, *, sans_erreur: bool = True, **etat: Any) -> AppTest:
        return _lancer(
            AppTest.from_file(str(RACINE / page)), etat, sans_erreur=sans_erreur
        )

    return _rendre


# ---------------------------------------------------------------------------
# Lecture du rendu
# ---------------------------------------------------------------------------
@pytest.fixture
def poids_apercu() -> Callable[[AppTest], list[float]]:
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


@pytest.fixture
def legendes_vignettes() -> Callable[[AppTest], list[str]]:
    """Légendes des images rendues dans la zone principale, dans l'ordre.

    On lit `at.main` et jamais `at` : VideoStatus peint une vignette en
    sidebar, qu'un `at.get("imgs")` global compterait en trop. Un élément
    `imgs` peut porter plusieurs images (st.image accepte une liste), d'où
    l'aplatissement.
    """

    def _legendes(at: AppTest) -> list[str]:
        return [img.caption for e in at.main.get("imgs") for img in e.proto.imgs]

    return _legendes
