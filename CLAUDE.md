# SimpleCut

Application Streamlit locale : on importe une vidéo, on choisit un segment, on en
fait un GIF animé. MoviePy 2.x décode, Pillow encode, `uv` gère les dépendances.

## Commandes

```bash
uv sync                       # installer les dépendances
uv run streamlit run App.py   # lancer l'application
uv run pytest                 # suite de tests
uv run ruff check .           # lint (configuré dans pyproject.toml)
uv add <pkg>                  # dépendance d'exécution
uv add --dev <pkg>            # dépendance de développement
```

## Vérifier avant de conclure

`uv run pytest` **et** `uv run ruff check .` doivent être verts avant d'annoncer
qu'une modification est terminée. La suite s'exécute en une seconde : il n'y a
aucune raison de s'en dispenser, ni de conclure sans l'avoir lancée.

## Conventions

- **Tout est en français** : libellés d'interface, commentaires, docstrings, noms
  de fonctions et de variables. Y compris dans un module neuf.
- **Modules en PascalCase** (`Layout.py`, `GifPanel.py`) : convention assumée du
  projet, la règle ruff `N999` n'est délibérément pas activée.
- `App.py` insère `src/` sur le `sys.path` : on importe `from utils.X import …`
  et `from components.X import …`, jamais `from src.utils.X`.
- Aucun formateur n'est branché et la longueur de ligne n'est pas contrôlée :
  suivre le style du fichier plutôt que le reformater au passage.
- **Aucune valeur de réglage écrite en dur dans ce fichier ni dans
  `.claude/rules/`.** Nombre de couleurs, largeur maximale, cadences, capacités
  de cache, seuils : citer la constante qui la porte, jamais sa valeur. Ces
  réglages bougent avec le projet ; une valeur recopiée ici deviendrait un
  mensonge sans que rien ne le signale.

## Architecture

- `App.py` — routeur `st.navigation`. La page GIF n'apparaît qu'une fois une
  vidéo chargée en session.
- `src/pages/` — une page = un script Streamlit exécuté de haut en bas.
- `src/components/` — briques d'interface partagées entre pages.
- `src/utils/` — la logique. Plusieurs de ces modules sont des **couches pures**,
  sans aucun import Streamlit, et doivent le rester : c'est ce qui les rend
  éprouvables sans `AppTest`. Leur docstring l'annonce explicitement.
- L'état de session se réduit à deux objets : la vidéo importée et le cache des
  GIFs produits. Pas de pile d'opérations, pas de drapeau d'affichage.

## Règles transverses

- **Une grandeur, un seul endroit qui la décide.** Calage d'affichage,
  dimensions de sortie, cadences proposées, instants de vignette : chacun a sa
  fonction dédiée. La recalculer ailleurs crée une divergence silencieuse.
- **MoviePy 2.x, pas 1.x** : les clips sont immuables, chaque opération renvoie
  une copie (`subclipped`, `resized`, `with_*`), et rien n'est décodé tant qu'un
  export n'est pas demandé.
- **Un aperçu qui échoue se dégrade**, il ne peint pas la page en rouge : une
  vignette illisible devient un `st.caption`. Le bandeau d'erreur est réservé à
  ce qui empêche réellement de continuer.
- **Tout fichier temporaire a un propriétaire désigné**, qui l'efface.
- Une modification de comportement s'accompagne de son test ; la suite couvre
  aussi bien les fonctions pures que les pages rendues sans navigateur.

## Où vit le reste

Les règles détaillées se chargent d'elles-mêmes depuis `.claude/rules/` : `src.md`
en travaillant dans `src/`, `tests.md` dans `tests/`. Le raisonnement derrière
chaque décision — mesures, alternatives écartées, pièges — vit dans la docstring
du module concerné. C'est là qu'il faut lire, pas ici.
