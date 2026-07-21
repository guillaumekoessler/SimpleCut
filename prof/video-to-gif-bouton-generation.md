# Prof — Générer le GIF depuis `VideoToGifs.py` (style callback de `Home.py`)

> Ce document t'accompagne pour **écrire toi-même** le code. Il ne contient aucun fichier prêt à
> copier-coller : des fragments illustrés, expliqués morceau par morceau, à assembler de ta main.

---

## 1. Besoin

Réécrire `src/pages/VideoToGifs.py` pour que :

1. la création du GIF soit déclenchée par un bouton **au style de `Home.py`** : un callback
   `on_click=...` qui **mute `st.session_state`**, jamais `if st.button(...)` ;
2. ce déclenchement appelle bien la fonction existante `_convert_video_to_gif(...)` ;
3. le tout soit **robuste** : pas de crash quand aucune vidéo n'est chargée, gestion des erreurs
   de conversion, cycle de vie propre des fichiers temporaires, résultat qui correspond
   toujours à la vidéo affichée.

**« Terminé » ressemble à :** j'importe une vidéo, je règle les curseurs, je clique « Créer le
GIF », je vois une phase de génération, puis un aperçu animé et un bouton de téléchargement. Sans
vidéo, la page ne plante pas. Si je change de vidéo source, l'ancien GIF ne s'affiche plus.

---

## 2. Approche retenue

**Le callback ne fait qu'une mutation rapide ; le corps du script fait le travail lourd.**

```
[clic bouton] → callback demander_generation(params)   ← RAPIDE : pose un "ticket" en session
                    └─ st.session_state["gif_request"] = params
[rerun] → corps du script
             ├─ détecte le ticket, le RETIRE (pop), génère le GIF avec progression
             └─ range le résultat en session → affiche aperçu + téléchargement
```

### Pourquoi ce découpage, et pas « tout dans le callback » ?

Vérifié via la doc Streamlit (context7) : **un callback `on_click` s'exécute *avant* le corps du
script**, puis le script est relancé de haut en bas. Un callback est donc l'endroit idéal pour une
**mutation d'état instantanée** (exactement ce que font `remove_video`, `start_replacing`,
`cancel_replacing` dans `Home.py`). En revanche, la doc recommande de **sortir les traitements
lourds du callback** : comme il tourne avant le rendu des widgets, tu ne peux pas y afficher
proprement une progression, et tu risques de relancer le calcul à chaque rerun.

D'où le patron **« ticket »** : le callback dépose une demande (les `ConversionParams` + le fait
qu'on veut générer), et c'est le corps — l'endroit normal pour dessiner l'UI — qui exécute la
conversion lente en montrant l'avancement.

### Alternatives écartées

- **`if st.button("Créer"): _convert_video_to_gif(...)`** — c'est le pattern « officiel » pour un
  traitement lourd, mais il **contredit ta contrainte** (reprendre le style sans `if st.button`).
  Le patron ticket t'offre le même bénéfice (travail lourd dans le corps) *tout en gardant* le
  `on_click`.
- **Tout dans le callback** — plus court à écrire, mais progression mal affichée et anti-pattern
  Streamlit pour une tâche longue. Écarté.

---

## 3. Fonctionnalités utilisées

| Outil | Ce que c'est | Pourquoi ici |
|---|---|---|
| `st.button(..., on_click=fn, args=(...))` | Bouton qui appelle `fn(*args)` **avant** le rerun. | Reproduit le style `Home.py`. `args` **fige** les valeurs du run courant (donc les params des curseurs au moment du rendu). |
| `st.session_state` | Dictionnaire persistant entre reruns. | Porte le « ticket » (`gif_request`) et le résultat (`gif_result`). |
| `st.session_state.pop(clé, défaut)` | Lit **et retire** une clé. | Consommer le ticket **une seule fois** : sans ça, il resterait actif et une interaction ultérieure quelconque relancerait la génération. |
| `st.stop()` | Interrompt proprement le rendu de la page. | Garde d'entrée quand aucune vidéo n'est chargée → plus de crash. |
| `st.button(..., disabled=...)` | Bouton grisé. | Empêcher le clic quand le segment est invalide. **Attention** : ne protège PAS la construction des params (voir §4, piège #1). |
| `st.status("…")` | Conteneur d'état extensible (spinner → complete/error). | Montrer la phase de génération. Provisoire : ce n'est pas un **pourcentage** (voir §5). |
| `st.image(bytes\|chemin)` | Affiche une image ; **anime les GIF**. | Aperçu du résultat. |
| `st.download_button(label, data, file_name, mime)` | Bouton de téléchargement de `data` (str/bytes). | Récupérer le GIF. Un clic déclenche un rerun mais **ne régénère pas** (le ticket a été `pop`é) et `gif_result` persiste. |
| `tempfile.mkstemp(suffix=".gif")` | Crée un fichier temporaire et rend `(fd, chemin)`. | Chemin de sortie du GIF. Préférable à `NamedTemporaryFile(delete=False)` : tu peux **fermer tout de suite** le descripteur avant que MoviePy écrive dessus. |
| `Path.unlink(missing_ok=True)` | Supprime un fichier sans lever s'il est absent. | Nettoyage des temporaires (ancien GIF, ou GIF partiel après erreur). |
| `Path(...).read_bytes()` / `Path(...).stem` | Lire les octets / le nom sans extension. | `data=` du download **et** `st.image` en une seule lecture ; `stem + ".gif"` pour un nom de fichier correct. |

---

## 4. Modifications pas à pas — `src/pages/VideoToGifs.py`

### Étape 0 — Nettoyer le fichier cassé

À supprimer :
- le stub `def create_gif( )` (lignes ~55-57) — il ne compile pas (`SyntaxError`) ;
- `st.button("Création du Gif", on_click=cancel_replacing)` — `cancel_replacing` n'existe pas ici ;
- le `st.write("Hello")` de fin.

Garde le `_convert_video_to_gif(...)` existant : il est correct et c'est **la fonction que tu
cherchais à appeler**.

### Étape 1 — Garde d'entrée (robustesse : ne pas planter sans vidéo)

Le code actuel fait `st.video(str(current.path))` alors que `current` peut être `None`. Ajoute, tout
de suite après avoir récupéré `current`, une garde :

```python
current: UploadedVideo | None = st.session_state.get("uploaded_video")

if current is None:
    st.info("Importez une vidéo pour commencer.", icon="🎬")
    st.stop()          # ← rien en dessous ne s'exécute : plus de crash
```

*Pourquoi `st.stop()` et pas un `if/else` géant ?* Ça aplatit le code : sous cette ligne, tu peux
supposer `current` non-`None`.

### Étape 2 — Construire les params… sans crasher sur un segment vide (piège #1, bloquant)

Le slider « Intervalle » est un **range slider** : les deux poignées peuvent se retrouver sur la
même valeur → `end_time == start_time`. Or `ConversionParams.__post_init__` **lève**
`ValueError("end_time doit être > start_time")`. Si tu construis l'objet inconditionnellement dans
le corps, **toute la page plante** — et `disabled=` sur le bouton n'y change rien, puisque la
construction a lieu *avant* le bouton.

La bonne façon : décider d'abord si le segment est valide, ne construire les params que dans ce cas.

```python
segment_valide = end_time > start_time

params = None
if segment_valide:
    params = ConversionParams(
        start_time=start_time,
        end_time=end_time,
        fps=fps,
        resize_factor=resize_factor,
    )
```

À toi d'écrire : le message d'aide quand `not segment_valide` (par ex. un `st.caption` qui invite à
élargir l'intervalle).

### Étape 3 — Le callback (style `Home.py`) + le bouton

Le callback est **minuscule** : il dépose le ticket. C'est tout.

```python
def demander_generation(params: ConversionParams) -> None:
    st.session_state["gif_request"] = params
```

Le bouton, en bas du bloc paramètres :

```python
st.button(
    "Créer le GIF",
    on_click=demander_generation,
    args=(params,),                 # tuple ! fige les params du run courant
    disabled=not segment_valide,    # confort UI ; la vraie protection est l'étape 2
)
```

**Pièges à connaître :**
- `args` doit être un **tuple** — `(params,)`, pas `(params)`.
- Ne mets **aucun** appel à `_convert_video_to_gif` ici. Le callback tourne avant le rendu : le
  travail lourd n'y a pas sa place.

### Étape 4 — Le corps consomme le ticket et génère (pièges #3 et #4)

Consomme le ticket avec `pop` (jamais `get` seul, sinon boucle infinie de génération), puis génère
dans un `st.status`. Points de robustesse à ne pas oublier, chacun signalé en commentaire ci-dessous.

```python
if st.session_state.get("gif_request") is not None:
    params = st.session_state.pop("gif_request")     # consommé UNE fois

    # (#4) mkstemp + close : on ne garde pas de handle ouvert pendant que MoviePy écrit
    fd, chemin_str = tempfile.mkstemp(suffix=".gif")
    os.close(fd)
    output_path = Path(chemin_str)

    # nettoyer un éventuel GIF précédent (voir étape 5 pour où le lire)
    _purger_ancien_gif()   # à toi de l'écrire à partir de gif_result

    with st.status("Génération du GIF…") as status:
        try:
            _convert_video_to_gif(current.path, output_path, params)
        except (FileNotFoundError, ValueError) as e:
            output_path.unlink(missing_ok=True)      # (#3) pas de GIF partiel qui traîne
            status.update(label=f"Échec : {e}", state="error")
        else:
            # (#2) on rattache le résultat à L'IDENTITÉ de la vidéo courante
            st.session_state["gif_result"] = (output_path, current.file_id)
            status.update(label="GIF prêt ✅", state="complete")
```

*Pourquoi `pop` avant la génération ?* Ainsi, même si la conversion échoue, le ticket est déjà
consommé : pas de nouvelle tentative en boucle au rerun suivant.

### Étape 5 — Afficher le résultat en le liant à la bonne vidéo (piège #2, important)

Ni `remove_video()` ni le remplacement de vidéo (tous deux dans `Home.py`) ne touchent à
`gif_result`. Sans précaution, après un changement de vidéo, l'ancien GIF s'afficherait pour la
nouvelle vidéo — un **résultat faux**, pas juste cosmétique. D'où le stockage `(chemin, file_id)`
à l'étape 4, et la vérification ici :

```python
resultat = st.session_state.get("gif_result")
if resultat is not None:
    chemin, file_id = resultat
    if file_id != current.file_id or not chemin.exists():
        # GIF issu d'une autre vidéo (ou temporaire disparu) → on purge
        chemin.unlink(missing_ok=True)
        st.session_state.pop("gif_result", None)
    else:
        octets = chemin.read_bytes()          # une seule lecture disque…
        st.image(octets)                       # …réutilisée pour l'aperçu…
        st.download_button(                    # …et pour le téléchargement
            "Télécharger le GIF",
            data=octets,
            file_name=f"{Path(current.name).stem}.gif",   # (#6) pas .mov !
            mime="image/gif",
        )
```

**Ce que tu résous ici :**
- **#2** : le GIF affiché correspond toujours à la vidéo courante (comparaison `file_id`).
- **#6** : `current.name` finit par `.mov` ; `Path(...).stem + ".gif"` donne un nom cohérent.
- **#7** : le garde `chemin.exists()` évite un crash si le temporaire a été purgé entre-temps.

### Imports à prévoir

Tu utiliseras `os` (pour `os.close`) en plus des imports déjà présents (`tempfile`, `Path`,
`ConversionParams`, `UploadedVideo`). Vérifie la liste en tête de fichier.

---

## 5. Un mot sur la « vraie » progression (finition #5)

`_convert_video_to_gif` appelle `write_gif(..., logger=None)`, donc `st.status` n'affiche qu'un
**spinner indéterminé**, pas de pourcentage. Ton `CLAUDE.md` rappelle que l'export GIF est
mono-thread et lent → l'idéal est un **pont `proglog.ProgressBarLogger` → `st.progress`**. Pour ce
premier jet, le spinner suffit ; assume-le comme provisoire. Quand tu voudras la barre chiffrée,
ce sera une évolution de `_convert_video_to_gif` (passer un logger au lieu de `None`), à traiter
séparément.

---

## 6. Vérification

Lance l'app : `uv run streamlit run App.py`, puis :

1. **Sans vidéo** → la page affiche l'invite et ne plante pas (garde `st.stop()`).
2. **Vidéo importée, segment normal** → clic « Créer le GIF » : phase de génération, puis aperçu
   animé + bouton de téléchargement. Le fichier téléchargé s'appelle `<nom>.gif`.
3. **Segment vide** (deux poignées collées) → bouton grisé, aucun crash même si tu forces l'état.
4. **Clic sur « Télécharger »** → le GIF se télécharge, l'aperçu reste, **aucune** régénération.
5. **Changer de vidéo** (Remplacer dans `Home.py`) → l'ancien aperçu disparaît ; un nouveau clic
   régénère pour la bonne vidéo. Vérifie qu'il ne reste pas de `.gif` orphelin
   (`ls $TMPDIR/*.gif`).
6. **Erreur provoquée** (par ex. `end_time` > durée en trafiquant les bornes) → `st.status` passe
   en état « error », pas de GIF partiel laissé sur le disque.

---

## Récapitulatif des pièges (checklist)

- [ ] #1 Ne construire `ConversionParams` que si `end_time > start_time` (le `disabled` ne protège pas).
- [ ] #2 Stocker `(chemin, file_id)` et n'afficher que si `file_id == current.file_id`.
- [ ] #3 `unlink(missing_ok=True)` du GIF sur le chemin d'erreur.
- [ ] #4 `mkstemp` + `os.close(fd)` plutôt qu'un handle ouvert.
- [ ] #5 `st.status` = spinner provisoire, pas un pourcentage.
- [ ] #6 `file_name = Path(current.name).stem + ".gif"`, `mime="image/gif"`.
- [ ] #7 Garde `chemin.exists()` avant `read_bytes()` / `st.image`.
- [ ] Callback = mutation rapide uniquement ; `pop` du ticket avant génération.

Quand tu auras écrit ta version, je peux la relire avec toi. 👍
