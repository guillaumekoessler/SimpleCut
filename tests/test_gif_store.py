"""Cache de GIFs : ressert le déjà-calculé, et ne laisse pas de fichier derrière."""

from pathlib import Path

from utils.GifClasses import ConversionParams, GifGenere
from utils.GifStore import CacheGifs


def _gif(dossier: Path, nom: str) -> GifGenere:
    """Un GifGenere adossé à un vrai fichier — le cache manipule le disque."""
    chemin = dossier / nom
    chemin.write_bytes(b"GIF89a" + b"\x00" * 10)
    return GifGenere(
        chemin=chemin,
        nb_images=1,
        largeur=1,
        hauteur=1,
        taille_octets=chemin.stat().st_size,
    )


def test_revenir_sur_les_memes_parametres_ressert_la_meme_entree(tmp_path):
    """La promesse tenue à l'utilisateur : mêmes params + même vidéo = pas de
    regénération. Tout le reste est un défaut de cache."""
    cache = CacheGifs()
    params = ConversionParams(0.0, 1.0, fps=10)
    autres_params = ConversionParams(0.0, 2.0, fps=10)
    gif = _gif(tmp_path, "a.gif")

    cache.deposer(("video-1", params), gif)

    assert cache.obtenir(("video-1", params)) is gif
    assert cache.obtenir(("video-1", autres_params)) is None
    assert cache.obtenir(("video-2", params)) is None


def test_l_eviction_efface_le_fichier_et_une_entree_fantome_est_ignoree(tmp_path):
    """Deux fuites possibles, fermées ici.

    1. L'éviction : sans unlink, chaque génération laisserait un GIF orphelin
       dans le dossier temporaire de l'OS pour toute la durée de la session.
    2. Le fantôme : le dossier temporaire peut être nettoyé sous nos pieds. Une
       entrée dont le fichier a disparu doit se comporter comme une absence,
       pas faire planter l'affichage.
    """
    cache = CacheGifs(capacite=2)
    params = [ConversionParams(0.0, float(i + 1), fps=10) for i in range(3)]
    gifs = [_gif(tmp_path, f"{i}.gif") for i in range(3)]

    for cle, gif in zip(params, gifs):
        cache.deposer(("video-1", cle), gif)

    assert len(cache) == 2
    assert not gifs[0].chemin.exists(), "le plus ancien doit être effacé du disque"
    assert cache.obtenir(("video-1", params[0])) is None
    assert gifs[1].chemin.exists() and gifs[2].chemin.exists()

    gifs[1].chemin.unlink()  # disparition dans le dos du cache

    assert cache.obtenir(("video-1", params[1])) is None
    assert len(cache) == 1


def test_changer_de_video_emporte_les_gifs_de_la_precedente(tmp_path):
    """Sans cette purge, les GIFs de l'ancienne vidéo resteraient en session ET
    sur le disque : plus rien ne générant pour leur file_id, plus rien ne les
    évincerait jamais. La page d'origine purgeait — ne pas le refaire serait
    une régression."""
    cache = CacheGifs()
    params = ConversionParams(0.0, 1.0, fps=10)
    ancien = _gif(tmp_path, "ancien.gif")
    nouveau = _gif(tmp_path, "nouveau.gif")
    cache.deposer(("video-1", params), ancien)
    cache.deposer(("video-2", params), nouveau)

    cache.purger_sauf("video-2")

    assert len(cache) == 1
    assert cache.obtenir(("video-2", params)) is nouveau
    assert not ancien.chemin.exists()
    assert nouveau.chemin.exists()
    assert cache.obtenir(("video-1", params)) is None
