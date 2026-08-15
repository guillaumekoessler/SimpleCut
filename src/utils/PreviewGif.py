"""Aperçu temps réel de l'intervalle GIF : bornes de boucle et temps de vignette.

Deux contraintes physiques pilotent ce module :
  - st.video tronque start_time/end_time à la seconde ENTIÈRE (int32 dans le
    proto) → la boucle doit englober la sélection, jamais l'amputer ;
  - demander une frame exactement à t == duree fait lire ffmpeg au-delà de la
    dernière frame → le temps de vignette est borné à duree - 1/fps.

Couche pure : zéro import Streamlit (même contrat que utils.Layout).
"""

from __future__ import annotations

import math

from utils.MathsVerif import _valider_fini, _valider_positive_finite

# Pas du slider « Intervalle » en secondes. Source unique de vérité : la page
# (step du slider) et l'arrondi des temps de vignette s'alignent dessus.
PAS_INTERVALLE = 0.1


def temps_vignette(
    t: float, duree: float, fps: float, pas: float = PAS_INTERVALLE
) -> float:
    """Temps normalisé auquel extraire une vignette.

    Arrondit t au pas du slider — deux positions visuellement identiques
    produisent la MÊME clé de cache — puis le borne dans [0, duree - 1/fps].

    Args:
        t: Instant demandé en secondes (valeur brute du slider). Seule la
            finitude est exigée : le signe est rattrapé par le bornage.
        duree: Durée de la vidéo en secondes (> 0, finie).
        fps: Cadence de la vidéo en images/s (> 0, finie).
        pas: Pas d'arrondi en secondes (> 0, fini).

    Returns:
        Un float dans [0, max(0, duree - 1/fps)].

    Raises:
        ValueError: Si duree, fps ou pas est <= 0 ou non fini, ou si t est
                    non fini (nan, inf).
    """
    _valider_positive_finite("duree", duree)
    _valider_positive_finite("fps", fps)
    _valider_positive_finite("pas", pas)
    # t n'est PAS contraint en signe : c'est une position de slider, que le
    # bornage ci-dessous ramène dans [0, plafond]. t == 0 est la position par
    # défaut (première frame) — la refuser vidait les deux vignettes au
    # chargement de la page, FramePreview attrapant le ValueError.
    _valider_fini("t", t)

    # round(t/pas)*pas réintroduit du bruit binaire (31 * 0.1 == 3.1000…05) :
    # le second round à 6 décimales normalise la clé de cache.
    arrondi = round(round(t / pas) * pas, 6)

    # max(0.0, …) : une vidéo plus courte qu'une frame ne doit pas produire
    # un plafond négatif.
    plafond = max(0.0, duree - 1.0 / fps)
    return min(max(arrondi, 0.0), plafond)


def bornes_boucle_video(debut: float, fin: float, duree: float) -> tuple[int, int]:
    """Bornes entières à passer à st.video pour boucler sur la sélection.

    floor(debut) et ceil(fin) : la boucle CONTIENT toujours [debut, fin].
    La borne haute peut dépasser la durée réelle (ceil) : sans danger, le
    frontend Streamlit gère l'événement `ended` et reboucle vers start_time.

    Args:
        debut: Borne basse de la sélection en secondes (0 <= debut <= fin).
        fin: Borne haute de la sélection en secondes (fin <= duree).
        duree: Durée de la vidéo en secondes (> 0, finie).

    Returns:
        (start_time, end_time) entiers, avec end_time >= start_time + 1
        — st.video ne doit jamais recevoir une boucle de durée nulle.

    Raises:
        ValueError: Si duree est invalide, si une borne est non finie,
                    négative, ou si l'ordre debut <= fin <= duree est violé.
    """
    _valider_positive_finite("duree", duree)
    # debut == 0.0 est la valeur par défaut du slider : le zéro doit passer.
    _valider_positive_finite("debut", debut, zero_autorise=True)
    _valider_positive_finite("fin", fin)

    if fin < debut:
        raise ValueError(f"fin ({fin!r}) doit être >= debut ({debut!r})")
    if fin > duree:
        raise ValueError(f"fin ({fin!r}) dépasse la durée de la vidéo ({duree!r})")

    borne_basse = math.floor(debut)
    borne_haute = max(math.ceil(fin), borne_basse + 1)
    return borne_basse, borne_haute
