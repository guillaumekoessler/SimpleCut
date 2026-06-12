# Guide d'implémentation — Visibilité de l'état « vidéo chargée »

Date : 2026-06-12
Spec associée : `2026-06-12-visibilite-video-chargee-design.md`
Référence Streamlit : `docs/reference-streamlit.md`

Ce guide détaille chaque modification, fichier par fichier, avec le code cible
et l'explication du raisonnement. Ordre conseillé : 1 → 2 → 3 → 4 (les fichiers
suivants dépendent des précédents).

---

## 1. `src/utils/VideoClasses.py` — enrichir le modèle de données

### Code cible

```python
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
    thumbnail: np.ndarray = field(compare=False)
```

### Explications

- **`name`** : le nom de fichier d'origine (`uploaded_file.name`). Le fichier
  temporaire sur disque a un nom aléatoire (`/tmp/tmpXXXX`), donc sans ce champ
  il est impossible d'afficher « ma_video.mov chargée ». C'est la pièce
  maîtresse de la visibilité.
- **`width` / `height` / `fps`** : lues sur le clip MoviePy déjà ouvert dans
  `_build_uploaded_video` — aucune lecture supplémentaire du fichier. `fps`
  servira aussi plus tard à la page Video→GIF (le fps du GIF doit diviser le
  fps source, cf. `IDEATION_GIF.md`).
- **`size_bytes`** : taille du fichier temporaire (`path.stat().st_size`).
  Stockée en octets bruts ; le formatage en Mo est une responsabilité de
  l'affichage, pas du modèle.
- **`thumbnail`** : la première frame de la vidéo, un `np.ndarray` de forme
  `(hauteur, largeur, 3)` retourné par `clip.get_frame(0)`. Affichable
  directement avec `st.image`, beaucoup plus léger qu'un lecteur vidéo.
- **`field(compare=False)` — important.** Un dataclass génère `__eq__` en
  comparant le tuple de ses champs. Or comparer deux `np.ndarray` avec `==`
  retourne un tableau de booléens, pas un booléen : Python lèverait
  `ValueError: The truth value of an array is ambiguous` à la première
  comparaison. De plus, `frozen=True` génère un `__hash__` à partir des champs
  comparés, et un ndarray n'est pas hashable. `compare=False` exclut le champ
  de `__eq__` **et** de `__hash__`, ce qui règle les deux problèmes. Les autres
  champs (dont `file_id`) suffisent à identifier une vidéo.
- L'import `numpy` est nécessaire pour l'annotation de type. MoviePy dépend
  déjà de numpy, donc rien à ajouter au `pyproject.toml`.

---

## 2. `src/components/video_status.py` — nouveau composant partagé

### Code cible (nouveau fichier)

```python
"""Statut global de la vidéo chargée, affiché dans la barre latérale."""

from __future__ import annotations

import streamlit as st

from utils.VideoClasses import UploadedVideo


def afficher_statut_video() -> None:
    """Affiche dans la sidebar l'état de la vidéo en session, sur toutes les pages."""
    video: UploadedVideo | None = st.session_state.get("uploaded_video")
    with st.sidebar:
        if video is not None:
            st.success(f"🎬 {video.name} · {video.duration:.0f} s")
        else:
            st.caption("Aucune vidéo chargée")
```

### Explications

- C'est le **premier composant de `src/components/`**, dont c'est exactement la
  vocation : un widget réutilisable par plusieurs pages.
- `st.session_state` est **partagé entre toutes les pages** d'une app
  multipage : c'est ce qui permet à la sidebar d'afficher le même état partout.
  Le composant ne lit que `st.session_state["uploaded_video"]` et n'écrit
  rien — c'est un affichage pur, sans effet de bord.
- `with st.sidebar:` redirige tout ce qui est rendu dans le bloc vers la barre
  latérale au lieu du corps de la page.
- L'import `from utils.VideoClasses import UploadedVideo` fonctionne car
  `App.py` insère `src/` dans `sys.path` (convention du projet).
- Chaque page doit appeler `afficher_statut_video()` **en tête de script** :
  en Streamlit, la sidebar n'existe que si la page en cours y dessine quelque
  chose à chaque exécution.

---

## 3. `src/pages/Home.py` — section d'import à états

C'est le gros morceau. Modifications dans l'ordre du fichier.

### 3.1 Imports

Ajouter :

```python
from components.video_status import afficher_statut_video
```

### 3.2 `_build_uploaded_video` — métadonnées et gestion d'erreur

```python
def _build_uploaded_video(uploaded_file) -> UploadedVideo | None:
    with tempfile.NamedTemporaryFile(delete=False) as tmp_video:
        tmp_video.write(uploaded_file.read())
        video_path = Path(tmp_video.name)

    try:
        with VideoFileClip(str(video_path)) as clip:
            duration = float(clip.duration)
            width, height = clip.size
            fps = float(clip.fps)
            thumbnail = clip.get_frame(0)
    except Exception:
        # Fichier illisible : on nettoie le temporaire et on signale l'échec.
        video_path.unlink(missing_ok=True)
        st.error("Impossible de lire cette vidéo.")
        return None

    return UploadedVideo(
        path=video_path,
        name=uploaded_file.name,
        duration=duration,
        width=width,
        height=height,
        fps=fps,
        size_bytes=video_path.stat().st_size,
        file_id=uploaded_file.file_id,
        thumbnail=thumbnail,
    )
```

Points clés :

- **Toutes les métadonnées sont extraites dans le même bloc `with`** : le clip
  n'est ouvert qu'une fois, et le `with` garantit la fermeture du process
  FFmpeg sous-jacent même en cas d'exception.
- **Le retour devient `UploadedVideo | None`** : `None` signifie « fichier
  illisible ». L'appelant (`video_uploader`) doit gérer ce cas.
- **Le `try/except` englobe toute la lecture MoviePy.** Si `VideoFileClip`
  échoue (fichier corrompu, format non vidéo malgré le filtre de l'uploader),
  on supprime le fichier temporaire **avant** de retourner, sinon il resterait
  orphelin sur le disque jusqu'au redémarrage de la machine.
- `clip.size` retourne `(largeur, hauteur)` — attention à l'ordre lors du
  dépaquetage.

### 3.3 `video_uploader` — spinner, toast, et ordre de suppression

```python
def video_uploader(
    label: str = "Importez votre vidéo",
) -> UploadedVideo | None:
    seed = st.session_state.get("uploader_seed", 0)
    uploaded_file = st.file_uploader(
        label,
        type="video/*",
        accept_multiple_files=False,
        label_visibility="hidden",
        key=f"home_video_uploader_{seed}",
    )

    cached: UploadedVideo | None = st.session_state.get("uploaded_video")

    if uploaded_file is None:
        return cached

    if cached is not None and cached.file_id == uploaded_file.file_id:
        return cached

    with st.spinner("Analyse de la vidéo…"):
        new_video = _build_uploaded_video(uploaded_file)

    if new_video is None:
        # Échec de lecture : on conserve la vidéo précédente telle quelle.
        return cached

    # On ne supprime l'ancien fichier qu'une fois le nouveau validé.
    if cached is not None:
        cached.path.unlink(missing_ok=True)

    st.toast("Vidéo importée ✅")
    return new_video
```

Points clés :

- **`st.spinner` n'entoure que la construction** (écriture du temporaire +
  ouverture MoviePy), pas l'affichage de l'uploader. Sur un `.mov` de
  plusieurs centaines de Mo, c'est la partie qui prend des secondes ; sans
  spinner la page paraît figée.
- **Changement d'ordre par rapport au code actuel — c'est un correctif de
  robustesse.** Aujourd'hui l'ancien fichier est supprimé *avant* de
  construire le nouveau. Si la construction échouait, la session pointerait
  vers un fichier supprimé. Le nouvel ordre est : construire → si succès,
  supprimer l'ancien → retourner le nouveau. En cas d'échec, on retombe sur
  `cached`, toujours intact.
- **`st.toast`** ne s'affiche qu'à l'import effectif d'un nouveau fichier
  (les deux `return cached` du début court-circuitent les re-exécutions où
  rien n'a changé).
- Le mécanisme `uploader_seed` existant est conservé tel quel : incrémenter le
  seed change la `key` du widget, ce qui force Streamlit à en créer un neuf
  (vide) après une suppression.

### 3.4 Callbacks d'état

`remove_video` gagne une ligne (remise à zéro du mode remplacement), et deux
petits callbacks apparaissent :

```python
def remove_video() -> None:
    cached: UploadedVideo | None = st.session_state.pop("uploaded_video", None)
    if cached is not None:
        cached.path.unlink(missing_ok=True)
    st.session_state.replacing = False
    st.session_state.uploader_seed = st.session_state.get("uploader_seed", 0) + 1


def start_replacing() -> None:
    st.session_state.replacing = True


def cancel_replacing() -> None:
    st.session_state.replacing = False
```

Pourquoi des callbacks (`on_click`) plutôt que `if st.button(...):` ? Un
callback s'exécute **avant** la ré-exécution du script. L'état est donc déjà à
jour quand la page se redessine : pas d'affichage intermédiaire incohérent ni
besoin d'un `st.rerun()` manuel.

### 3.5 En-tête de page

Ajouter l'appel sidebar avant le titre :

```python
afficher_statut_video()

st.title("SimplCut", text_alignment="center")
st.caption("Convertissez une vidéo .mov en GIF animé", text_alignment="center")
st.divider()
```

### 3.6 Section IMPORT à états (remplace les sections actuelles Upload + le bouton de l'aperçu)

```python
current: UploadedVideo | None = st.session_state.get("uploaded_video")
replacing: bool = st.session_state.get("replacing", False)

with st.container(border=True):
    st.caption("IMPORT")

    if current is None or replacing:
        # État « pas de vidéo » (ou remplacement en cours) : on montre l'uploader.
        video = video_uploader()
        if replacing:
            st.button("Annuler", on_click=cancel_replacing)
        if video is not None and video is not current:
            st.session_state.uploaded_video = video
            st.session_state.replacing = False
            st.rerun()
    else:
        # État « vidéo chargée » : carte de statut à la place de l'uploader.
        st.success(f"✅ {current.name} chargée — {current.duration:.1f} s")

        col_vignette, col_metriques = st.columns([1, 3], vertical_alignment="center")
        with col_vignette:
            st.image(current.thumbnail, width="stretch")
        with col_metriques:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Durée", f"{current.duration:.1f} s")
            m2.metric("Dimensions", f"{current.width}×{current.height}")
            m3.metric("FPS", f"{current.fps:.0f}")
            m4.metric("Poids", f"{current.size_bytes / 1_000_000:.1f} Mo")

        col_remplacer, col_supprimer = st.columns(2)
        col_remplacer.button("Remplacer", on_click=start_replacing, width="stretch")
        col_supprimer.button(
            "Supprimer la vidéo", on_click=remove_video, width="stretch"
        )
```

Points clés :

- **Deux états exclusifs.** Soit l'uploader, soit la carte de statut — jamais
  les deux. C'est ce qui supprime l'ambiguïté actuelle « uploader vide alors
  qu'une vidéo est chargée » au retour sur la page.
- **Le flag `replacing`** ré-affiche l'uploader sans toucher à la vidéo en
  cours : si l'utilisateur change d'avis (« Annuler ») ou si le nouveau
  fichier est illisible, rien n'est perdu. La logique de `video_uploader`
  supprime l'ancien fichier temporaire seulement quand un nouveau `file_id`
  est validé.
- **`video is not current`** compare l'**identité** des objets, pas leur
  égalité. `video_uploader` retourne soit l'objet déjà en session (mêmes
  `return cached`), soit un objet neuf. L'identité distingue les deux cas sans
  aucune comparaison de champs : objet neuf → on le stocke et on relance.
- **Pourquoi `st.rerun()` ici ?** Le script s'exécute de haut en bas ; au
  moment où l'upload est traité, la sidebar et le haut de page ont déjà été
  dessinés avec l'ancien état. `st.rerun()` relance immédiatement le script
  pour que tout (sidebar, carte de statut, aperçu) reflète la nouvelle vidéo
  dans la même interaction. Il remplace l'ancien mécanisme `first_upload`.
- **`width="stretch"`** : c'est le paramètre actuel pour étirer un élément à
  la largeur de sa colonne. `use_container_width` est déprécié (voir la
  référence Streamlit).
- Remarque : `current` lu en haut reste valable dans toute la suite du script.
  Tous les chemins qui modifient la vidéo passent soit par un callback
  (exécuté avant le script), soit par `st.rerun()` (qui relance le script).

### 3.7 Section APERÇU allégée

Le bouton « Supprimer la vidéo » part dans la carte de statut ; l'aperçu ne
garde que le lecteur :

```python
if current is not None:
    with st.container(border=True):
        st.caption("APERÇU")
        st.video(str(current.path))
else:
    st.info("Importez une vidéo pour commencer.", icon="🎬")
```

### 3.8 Code supprimé

- Le bloc `if video is not None: first_upload = ...` après le container
  d'upload (remplacé par la logique de la section 3.6).
- Le `st.button("Supprimer la vidéo", ...)` de la section aperçu (déplacé dans
  la carte de statut).

---

## 4. `src/pages/VideoToGifs.py` — brancher la sidebar

```python
import streamlit as st

from components.video_status import afficher_statut_video

afficher_statut_video()

st.write("Hello")
```

La page est encore un brouillon ; seul l'appel sidebar compte. Toute future
page devra faire de même en tête de script.

---

## 5. Checklist de vérification manuelle

Lancer `uv run streamlit run App.py`, puis :

1. **Import** : uploader visible, spinner « Analyse de la vidéo… » pendant le
   chargement, toast « Vidéo importée ✅ », puis carte de statut (bandeau vert,
   vignette, 4 métriques) et sidebar à jour.
2. **Navigation** : aller sur VideoToGifs puis revenir sur Home. La carte de
   statut doit s'afficher directement (pas d'uploader vide), la sidebar doit
   être cohérente sur les deux pages.
3. **Remplacer** : l'uploader réapparaît avec « Annuler ». Importer un autre
   fichier → la carte montre le nouveau nom ; vérifier dans `/tmp` que
   l'ancien fichier temporaire a disparu. « Annuler » → retour à la carte sans
   rien perdre.
4. **Supprimer** : retour à l'état vide (uploader + message d'invite), sidebar
   « Aucune vidéo chargée ». Ré-importer le **même** fichier doit fonctionner
   (c'est le rôle de `uploader_seed`).
5. **Fichier illisible** : renommer un fichier texte en `.mov` et l'importer →
   message « Impossible de lire cette vidéo. », état précédent conservé, pas
   de temporaire orphelin.
