# Référence Streamlit — fonctions utilisées dans SimpleCut

Documentation des fonctions Streamlit employées dans le projet, avec leur rôle
précis dans notre code. Pour la référence exhaustive : https://docs.streamlit.io

## Le modèle d'exécution (à comprendre avant tout)

Streamlit n'a ni boucle d'événements ni système de vues : **le script entier
est ré-exécuté de haut en bas à chaque interaction** (clic, upload, changement
de page). Trois conséquences structurent tout notre code :

1. Une variable Python locale ne survit pas entre deux interactions — d'où
   `st.session_state` pour tout ce qui doit persister.
2. L'interface affichée est exactement ce que le script a dessiné lors de la
   dernière exécution. Pour changer d'affichage, on change l'état puis on
   laisse (ou force) une ré-exécution.
3. L'ordre dans le script est l'ordre à l'écran. Si un état change *après*
   qu'un élément a été dessiné (ex. la sidebar), il faut `st.rerun()` pour le
   voir dans la même interaction.

---

## État et cycle de vie

### `st.session_state`

Dictionnaire persistant pendant toute la session du navigateur, **partagé
entre toutes les pages** de l'app multipage. Accès par clé
(`st.session_state["x"]`) ou attribut (`st.session_state.x`).

Dans SimpleCut : porte `uploaded_video` (l'objet `UploadedVideo`),
`uploader_seed` (compteur pour réinitialiser l'uploader) et `replacing`
(mode remplacement). C'est le partage entre pages qui permet à la sidebar
d'afficher le même statut partout.

À savoir : `.get(clé, défaut)` évite les `KeyError` à la première exécution ;
`.pop(clé, défaut)` lit et supprime en une opération (utilisé dans
`remove_video`).

### `st.rerun()`

Interrompt l'exécution du script et le relance immédiatement depuis le début.
À utiliser quand un état change *en cours de script* alors que des éléments
déjà dessinés (sidebar, haut de page) devraient le refléter.

Dans SimpleCut : appelé juste après l'enregistrement d'une nouvelle vidéo en
session, pour que la sidebar et la carte de statut s'affichent à jour dans la
même interaction. Attention : tout code situé après `st.rerun()` n'est jamais
exécuté.

### Callbacks `on_click`

Tout widget interactif accepte `on_click=` (ou `on_change=`) : la fonction est
exécutée **avant** la ré-exécution du script. Quand le script redémarre,
l'état est donc déjà cohérent — pas besoin de `st.rerun()` dans un callback
(il y est d'ailleurs interdit).

Dans SimpleCut : `remove_video`, `start_replacing`, `cancel_replacing` sont
des callbacks. C'est la différence avec le style `if st.button(...):` où le
code s'exécute *pendant* la ré-exécution, après que le haut de la page a déjà
été dessiné avec l'ancien état.

---

## Widgets d'entrée

### `st.file_uploader(label, type=..., accept_multiple_files=..., label_visibility=..., key=...)`

Zone de glisser-déposer. Retourne `None` tant que rien n'est uploadé, sinon un
objet `UploadedFile` (sous-classe de `BytesIO`) avec :

- `.name` : nom de fichier d'origine (« ma_video.mov ») ;
- `.file_id` : identifiant unique régénéré à chaque upload — c'est notre clé
  de déduplication entre ré-exécutions ;
- `.read()` : contenu binaire. MoviePy/FFmpeg exigeant un vrai fichier sur
  disque, on recopie ce contenu dans un `tempfile.NamedTemporaryFile`.

Le paramètre `key` identifie le widget d'une exécution à l'autre. **Changer la
key détruit le widget et en crée un neuf, vide** : c'est le mécanisme
`uploader_seed` — incrémenter le seed après une suppression vide l'uploader,
ce qui permet aussi de ré-importer le même fichier ensuite.

### `st.button(label, on_click=..., width=...)`

Retourne `True` pendant la seule ré-exécution qui suit le clic. Nous utilisons
plutôt `on_click` (voir Callbacks ci-dessus). `width="stretch"` étire le
bouton à la largeur de sa colonne.

---

## Mise en page

### `st.container(border=True)`

Groupe visuel ; `border=True` dessine un encadré. S'utilise en gestionnaire de
contexte : tout ce qui est appelé sous `with st.container(...):` est rendu
dedans. Structure nos sections IMPORT et APERÇU.

### `st.columns(spec, vertical_alignment=...)`

Découpe la largeur en colonnes. `spec` est soit un entier (colonnes égales),
soit une liste de poids relatifs : `st.columns([1, 3])` donne une colonne à
1/4 et une à 3/4 (vignette vs métriques). Chaque colonne s'utilise en `with`
ou en notation objet (`col.metric(...)`, `col.button(...)`).
`vertical_alignment="center"` centre verticalement les contenus des colonnes
entre eux.

### `st.sidebar`

Barre latérale, persistante visuellement entre les pages mais **redessinée par
chaque page** : d'où la convention d'appeler `afficher_statut_video()` en tête
de chaque script de page. S'utilise en `with st.sidebar:` pour y rediriger un
bloc d'éléments.

---

## Affichage

### `st.title(texte, text_alignment=...)` / `st.caption(texte)` / `st.divider()`

Titre principal, texte secondaire grisé (nos étiquettes « IMPORT »,
« APERÇU »), trait horizontal.

### `st.metric(label, value)`

Affiche une valeur en gros caractères avec son étiquette au-dessus. Le
paramètre `value` est une chaîne déjà formatée — c'est nous qui formatons
(`f"{duration:.1f} s"`, `f"{size_bytes / 1_000_000:.1f} Mo"`). Accepte aussi
`delta=` pour afficher une variation (inutilisé ici).

### `st.image(image, width=...)`

Affiche une image. Accepte directement un `np.ndarray` `(H, W, 3)` en RGB —
exactement ce que retourne `clip.get_frame(0)` de MoviePy, aucune conversion
nécessaire. `width="stretch"` adapte l'image à la largeur de sa colonne.

### `st.video(source)`

Lecteur vidéo avec contrôles (lecture, pause, plein écran). Accepte un chemin
de fichier local sous forme de chaîne — d'où `st.video(str(current.path))`.

---

## Messages d'état

### `st.success(texte)` / `st.info(texte, icon=...)` / `st.error(texte)`

Bandeaux colorés persistants (vert / bleu / rouge). Notre code de couleur :

- `st.success` : vidéo chargée (carte de statut, sidebar) ;
- `st.info` : invite quand rien n'est chargé ;
- `st.error` : fichier illisible.

### `st.spinner(texte)`

Gestionnaire de contexte : affiche un indicateur d'activité tant que le bloc
`with` s'exécute, puis le retire. Entoure `_build_uploaded_video` (écriture du
fichier temporaire + ouverture MoviePy), qui peut prendre plusieurs secondes
sur un gros `.mov`.

### `st.toast(texte)`

Notification éphémère en bas à droite, qui disparaît seule au bout de
quelques secondes. Parfaite pour confirmer un succès sans occuper la page
(« Vidéo importée ✅ »). Ne pas y mettre d'information durable : un toast
manqué est perdu.

---

## Paramètre `width` (remplace `use_container_width`)

Depuis les versions récentes de Streamlit, les éléments (boutons, images,
tableaux…) acceptent un paramètre unifié `width` :

- `width="stretch"` : occupe toute la largeur du conteneur parent ;
- `width="content"` : largeur naturelle du contenu ;
- `width=300` : largeur fixe en pixels.

Les anciens booléens `use_container_width=` et `use_column_width=` sont
**dépréciés** : ne plus les utiliser dans le nouveau code.
