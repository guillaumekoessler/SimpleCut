---
paths:
  - "tests/**"
---

# Écrire un test dans SimpleCut

`uv run pytest` lance tout, et la suite est rapide : la lancer entièrement est le
défaut, pas une précaution.

## Prendre ce que conftest.py fournit déjà

Ne pas réécrire ce montage dans un fichier de test — le demander en fixture :

- `fabrique_video(...)` — construit un `UploadedVideo`. Tous les champs ont un
  défaut ; ne surcharger que ce que le test éprouve vraiment. Adossé par défaut à
  un fichier factice, suffisant pour `st.video` et qui sert aussi à éprouver le
  chemin d'échec du décodage.
- `video_reelle`, `clip_reel`, `fabrique_clip` — pour les tests qui décodent
  réellement des images. Les clips sont **générés**, jamais commités.
- `rendre_app(...)` / `rendre_page(...)` — amorcent `session_state` puis exécutent
  un `AppTest`. Les deux vérifient déjà l'absence d'exception ; un test qui en
  attend une passe `sans_erreur=False` et l'affirme lui-même.
- `poids_apercu(at)`, `legendes_vignettes(at)` — lecture du rendu, structurelle et
  non positionnelle : les pages gagnent des colonnes, un index en dur ne tient pas.

## Pièges

- **`AppTest.from_function` ré-exécute le code source de la fonction** comme un
  script isolé : aucune fermeture ne survit. Les imports vont **dans le corps** de
  la fonction, et un objet ne lui parvient que par `args` / `kwargs`.
- `args`, `kwargs` et `sans_erreur` sont réservés : ils ne peuvent pas servir de
  clé de `session_state` dans un appel à `rendre_app`.
- **`@pytest.mark.parametrize` est évalué à la collecte** et ne sait pas consommer
  une fixture : tout jeu de données paramétré vit dans `tests/donnees.py`, jamais
  dans `conftest.py`.
- Compter les éléments dans `at.main` et non dans `at` : la barre latérale en
  peint aussi, et ils seraient comptés en trop.
- Un `st.cache_data` est global au processus. Alimenté par une fixture de session,
  il faut le vider entre les tests — sans quoi l'ordre d'exécution devient
  signifiant.
