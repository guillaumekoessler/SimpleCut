# Design — Visibilité de l'état « vidéo chargée »

Date : 2026-06-12
Portée : `src/pages/Home.py`, `src/utils/VideoClasses.py`, `src/components/`, `src/pages/VideoToGifs.py`

## Objectif

L'utilisateur doit savoir d'un seul coup d'œil, sur n'importe quelle page, si une vidéo est chargée et laquelle. Aujourd'hui, l'uploader vide et l'aperçu coexistent sans lien : au retour sur la page Home, l'uploader s'affiche vide alors qu'une vidéo est en mémoire, et aucune métadonnée (nom, durée, dimensions) n'est affichée.

## Contrainte d'interface

Utiliser les éléments Streamlit natifs (`st.success`, `st.metric`, `st.image`, `st.button`, …). Pas de `st.markdown` ni de chaînes markdown dans les éléments, sauf si aucun élément natif ne couvre le besoin. Textes d'interface et commentaires en français.

## 1. Modèle de données — `src/utils/VideoClasses.py`

`UploadedVideo` enrichi. Toutes les valeurs sont disponibles sans coût supplémentaire : le clip est déjà ouvert dans `_build_uploaded_video` et `uploaded_file.name` existe.

```python
@dataclass(frozen=True, slots=True)
class UploadedVideo:
    path: Path
    name: str            # uploaded_file.name, ex. "ma_video.mov"
    duration: float
    width: int
    height: int
    fps: float
    size_bytes: int      # taille du fichier temporaire sur disque
    file_id: str
    thumbnail: np.ndarray = field(compare=False)  # première frame, clip.get_frame(0)
```

`compare=False` sur `thumbnail` pour éviter qu'un `__eq__` de dataclass ne tente de comparer des ndarrays (ambiguïté de valeur de vérité numpy).

## 2. Section d'import à états — `src/pages/Home.py`

Le container IMPORT devient exclusif, piloté par `st.session_state` :

- Aucune vidéo chargée : uploader actuel, plus le `st.info` d'invite existant.
- Vidéo chargée : carte de statut à la place de l'uploader, composée de :
  - `st.success` avec nom et durée, ex. « ✅ ma_video.mov chargée — 12,3 s » ;
  - vignette (`st.image(thumbnail)`) en miniature à côté d'une rangée de `st.metric` : durée, dimensions, fps, poids (formaté en Mo) ;
  - deux boutons : « Remplacer » (active un flag `replacing` en session qui ré-affiche l'uploader ; la logique existante de `video_uploader` gère déjà la suppression de l'ancien fichier temporaire quand le `file_id` change) et « Supprimer la vidéo » (le `remove_video` actuel, déplacé ici depuis la section aperçu).
- La section APERÇU conserve le lecteur `st.video` complet, sans le bouton supprimer.

## 3. Feedback de chargement

- `_build_uploaded_video` enveloppé dans `st.spinner("Analyse de la vidéo…")`.
- Confirmation par `st.toast("Vidéo importée ✅")` après succès.
- En cas d'échec de `VideoFileClip` (fichier corrompu ou illisible) : `st.error("Impossible de lire cette vidéo.")`, suppression du fichier temporaire, état inchangé.

## 4. Statut global en sidebar — `src/components/video_status.py`

Premier composant partagé du projet :

```python
def afficher_statut_video() -> None:
    # lit st.session_state["uploaded_video"] et affiche dans st.sidebar :
    # « 🎬 ma_video.mov · 12 s » si chargée, sinon « Aucune vidéo chargée »
```

Appelé depuis `Home.py` et `VideoToGifs.py`. Seul point de contact entre pages ; tout passe par `st.session_state`, conformément au modèle de session de la spec IDEATION.

## 5. Vérification

Pas de runner de tests dans le projet. Vérification manuelle via `uv run streamlit run App.py` :

1. Upload d'une vidéo : spinner pendant l'analyse, toast, carte de statut avec métadonnées et vignette.
2. Navigation Home → VideoToGifs → Home : la carte de statut et la sidebar restent cohérentes, pas d'uploader vide trompeur.
3. Remplacer : l'uploader réapparaît, le nouvel upload remplace l'ancien et supprime l'ancien fichier temporaire.
4. Supprimer : retour à l'état vide, re-upload possible (le mécanisme `uploader_seed` existant doit continuer de fonctionner).
5. Fichier illisible : message d'erreur, pas de fichier temporaire orphelin.
