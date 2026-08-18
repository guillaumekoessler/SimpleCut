"""Cache des GIFs déjà produits, adressé par (identité vidéo, paramètres).

Deux besoins tenus par une seule structure :

  - **ne pas refaire un travail déjà payé** — revenir sur des réglages déjà
    exportés doit réafficher le GIF instantanément, sans repasser par MoviePy ;
  - **ne pas laisser s'accumuler des fichiers temporaires** — d'où un cache
    BORNÉ dont l'éviction efface le fichier du disque.

Couche pure : aucun import Streamlit. L'instance vit dans `st.session_state`,
donc une par session utilisateur — la bonne portée, un fichier temporaire
n'ayant de sens que pour la session qui l'a créé.
"""

from __future__ import annotations

from utils.GifClasses import ConversionParams, GifGenere

# Un GIF est identifié par la vidéo dont il sort ET les réglages qui l'ont
# produit. Le file_id (et non le chemin) parce qu'un chemin de tempfile peut
# être recyclé par l'OS — même raisonnement que la clé de cache des vignettes.
CleGif = tuple[str, ConversionParams]

# Nombre de GIFs gardés simultanément. Assez pour qu'un aller-retour entre deux
# ou trois réglages soit gratuit, assez peu pour que le disque ne gonfle pas.
CAPACITE_DEFAUT = 4


class CacheGifs:
    """Cache LRU borné de GIFs sur disque.

    Args:
        capacite: Nombre maximal de GIFs conservés (>= 1).

    Raises:
        ValueError: Si capacite < 1.
    """

    def __init__(self, capacite: int = CAPACITE_DEFAUT) -> None:
        if capacite < 1:
            raise ValueError(f"capacite doit être >= 1, reçu : {capacite!r}")
        self._capacite = capacite
        # dict ordonné par insertion : le plus ancien est en tête.
        self._entrees: dict[CleGif, GifGenere] = {}

    def __len__(self) -> int:
        return len(self._entrees)

    def obtenir(self, cle: CleGif) -> GifGenere | None:
        """Le GIF produit pour cette clé, ou None s'il n'y en a pas.

        Une entrée dont le fichier a disparu (nettoyage du dossier temporaire
        par l'OS) est traitée comme une absence, et oubliée au passage : mieux
        vaut regénérer que planter à l'affichage.
        """
        gif = self._entrees.get(cle)
        if gif is None:
            return None

        if not gif.chemin.exists():
            del self._entrees[cle]
            return None

        # Rafraîchit l'ancienneté : le plus récemment servi repart en queue,
        # donc sera le dernier évincé.
        self._entrees[cle] = self._entrees.pop(cle)
        return gif

    def deposer(self, cle: CleGif, gif: GifGenere) -> None:
        """Range un GIF, en évinçant le plus ancien si la capacité est atteinte.

        L'éviction efface le fichier : c'est le seul endroit du programme qui
        supprime un GIF réussi, donc le seul à surveiller pour comprendre la
        durée de vie des fichiers temporaires.
        """
        remplace = self._entrees.pop(cle, None)
        if remplace is not None and remplace.chemin != gif.chemin:
            remplace.chemin.unlink(missing_ok=True)

        self._entrees[cle] = gif

        while len(self._entrees) > self._capacite:
            plus_ancienne = next(iter(self._entrees))
            self._entrees.pop(plus_ancienne).chemin.unlink(missing_ok=True)

    def purger_sauf(self, file_id: str) -> None:
        """Oublie et efface tous les GIFs qui ne viennent pas de cette vidéo.

        Sans cet appel, changer de vidéo laisserait les GIFs de la précédente
        en session ET sur le disque : plus rien ne générant pour leur file_id,
        plus rien ne les évincerait jamais. La page d'origine purgeait au
        changement de vidéo — ne pas le refaire serait une régression.
        """
        etrangers = [cle for cle in self._entrees if cle[0] != file_id]
        for cle in etrangers:
            self._entrees.pop(cle).chemin.unlink(missing_ok=True)
