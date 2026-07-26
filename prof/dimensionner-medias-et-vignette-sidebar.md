# Dimensionner les aperçus média + refondre la vignette de la sidebar

> Guide d'implémentation — **tu écris le code toi-même**. Ce document ne contient que des extraits pédagogiques à comprendre puis retaper. Aucune modification n'a été faite dans tes fichiers.

---

## 1. Besoin

Deux problèmes distincts :

1. **Les médias sont parfois trop grands** (surtout en portrait : une vidéo verticale s'affiche démesurément haute). Tu veux **figer leur taille** pour un rendu correct sur mobile **et** ordinateur.
2. **La vignette** doit être **plus petite** et doit **remplacer le 🎬** dans la barre latérale.

**Périmètre décidé ensemble** — on borne **4 rendus média** en largeur fixe, plus la refonte de la sidebar :

| #   | Fichier                         | Ligne actuelle | Rendu                                                                               |
| --- | ------------------------------- | -------------- | ----------------------------------------------------------------------------------- |
| S1  | `src/pages/VideoToGifs.py`      | 153            | `st.image(octets)` — aperçu du GIF généré (**le coupable principal**)               |
| S2  | `src/pages/VideoToGifs.py`      | 75             | `st.video(str(current.path))` — vidéo source                                        |
| S3  | `src/pages/Home.py`             | 134            | `st.image(current.thumbnail, width="stretch")` — vignette du bloc « vidéo chargée » |
| S4  | `src/pages/Home.py`             | 152            | `st.video(str(current.path))` — vidéo source                                        |
| S5  | `src/components/VideoStatus.py` | 14–18          | `st.success(f"🎬 {name} · {dur} s")` — statut sidebar                               |

**« Terminé » signifie :**

- Les 4 médias ont une taille bornée et prévisible ; **aucun débordement horizontal sur mobile** ; une vidéo portrait n'occupe plus tout l'écran en hauteur.
- La sidebar affiche une **petite vignette à gauche** du bandeau vert (`nom · durée`) ; **le 🎬 a disparu**.
- **Éléments Streamlit natifs uniquement** (pas de `st.markdown`, pas de HTML) — conforme à ta préférence.
- Tests automatiques au vert + contrôle visuel desktop **et** mobile.

---

## 2. Approche retenue

**Largeur fixe en pixels** via le paramètre natif `width`, présent sur `st.image` **et** `st.video` en Streamlit 1.57 (vérifié dans ton environnement). Les valeurs sont centralisées dans un petit module de constantes.

**Sidebar** : on ne peut **pas** insérer une image _dans_ un `st.success`. On construit donc une mise en page native `st.columns([1, 3])` : vignette à gauche, bandeau vert à droite. C'est **exactement le motif déjà utilisé** dans `Home.py:132-134` — donc éprouvé dans ton propre code.

### Alternatives écartées

| Alternative                                                          | Pourquoi écartée                                                                                                                          |
| -------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `width="stretch"` partout                                            | Remplit le conteneur (responsive) mais **agrandit/floute** les petits médias et laisse les portraits très hauts. Tu as choisi le px fixe. |
| CSS `max-width`/`max-height` (`st.markdown(unsafe_allow_html=True)`) | Violerait ta règle « natif only ». Et **inutile** : le paramètre `width` natif suffit.                                                    |
| Constantes locales dans chaque fichier                               | Possible, mais 4 valeurs réparties sur 3 fichiers → un module partagé rend le réglage cohérent (un seul endroit à ajuster).               |

### Tension assumée (à connaître)

Une largeur **fixe** est prévisible, mais :

- elle peut paraître **petite sur un grand écran** desktop (un GIF de 480 px au milieu d'une zone de ~730 px) ;
- elle n'est « optimale sur mobile » **que si** Streamlit ramène une largeur fixe > écran à la largeur du conteneur (`max-width: 100%`). **Ce comportement n'est pas vérifiable en Python** — c'est la seule inconnue du plan.

👉 Mitigation : on **valide ce comportement sur un seul site d'abord** (le GIF), puis on déroule les 3 autres. Si le clamp n'a pas lieu (débordement mobile), on bascule sur le **repli responsive garanti** (voir §6, encadré).

---

## 3. Fonctionnalités utilisées

_(Signatures vérifiées via la doc officielle Streamlit et par introspection dans ton venv — Streamlit 1.57.0.)_

- **`st.image(image, …, width='content')`** — `width` accepte `int` (pixels), `"stretch"` (remplit le conteneur) ou `"content"` (taille naturelle, défaut). `int` = notre largeur fixe. `use_column_width`/`use_container_width` sont l'**ancienne** voie, dépréciée : on ne les utilise pas.
- **`st.video(data, …, *, width='stretch')`** — `width` accepte `int` ou `"stretch"` (**pas** `"content"`). Défaut `"stretch"` : c'est pourquoi tes vidéos remplissent déjà tout le conteneur aujourd'hui. On passe un `int`.
- **`st.columns([1, 3], vertical_alignment="center")`** — colonnes côte à côte natives ; `vertical_alignment="center"` centre verticalement la vignette par rapport au bandeau.
- **`st.success(texte)`** — bandeau vert natif « chargé ». ⚠️ **Streamlit extrait l'emoji de tête dans le champ `.icon`**, pas dans le texte. `st.success("🎬 ma_video · 5 s")` donne `value="ma_video · 5 s"`, `icon="🎬"`. C'est décisif pour le test (§4).
- **`streamlit.testing.v1.AppTest`** — banc de test **natif** de Streamlit. `AppTest.from_function(callable)` (les imports doivent être **dans** le corps de la fonction), `at.session_state[...] = …` avant `at.run()`, `assert not at.exception`, accès aux éléments : `at.sidebar.success[0].icon` / `.value`, `at.sidebar.caption[0].value`.
- **`pytest`** — lanceur de tests (à ajouter en dépendance de dev).

---

## 4. Tests d'abord (TDD)

On écrit les tests **avant** de modifier `VideoStatus.py`. Le point porteur : **le test doit pouvoir échouer** avec le code actuel, sinon il ne prouve rien.

### 4.1 Outillage (à faire une fois)

```bash
uv add --dev pytest
```

Puis crée `tests/conftest.py` pour que `from components…` / `from utils…` fonctionnent dans les tests, comme le fait `App.py` :

```python
# tests/conftest.py
import sys
from pathlib import Path

# Miroir de App.py : on insère src/ sur le sys.path pour importer
# components/ et utils/ comme des packages de premier niveau.
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
```

### 4.2 Test de contrat des dimensions — `tests/test_ui_dimensions.py`

```python
from utils.Dimensions import (
    LARGEUR_APERCU_GIF,
    LARGEUR_APERCU_VIDEO,
    LARGEUR_VIGNETTE_ACCUEIL,
    LARGEUR_VIGNETTE_SIDEBAR,
)


def test_dimensions_sont_des_entiers_plausibles():
    for valeur in (
        LARGEUR_APERCU_GIF,
        LARGEUR_APERCU_VIDEO,
        LARGEUR_VIGNETTE_ACCUEIL,
        LARGEUR_VIGNETTE_SIDEBAR,
    ):
        assert isinstance(valeur, int)
        assert 16 <= valeur <= 2000
```

**Honnêteté sur sa portée :** ce test attrape une **faute de frappe dans le fichier de constantes** (un `"480"` chaîne, un `4800` aberrant). Il **ne vérifie pas** le bon câblage au site d'appel (par ex. intervertir GIF et VIDEO). Ce n'est pas une couverture comportementale — juste un garde-fou bon marché.

### 4.3 Test comportemental de la sidebar — `tests/test_video_status.py`

C'est le **vrai** test rouge→vert. Deux subtilités à ne pas rater :

**(a) Le wrapper `from_function`.** Tu ne peux **pas** passer directement `afficher_statut_video` à `from_function` : Streamlit extrait le _source_ de la fonction et l'exécute hors des globals de `VideoStatus` → `NameError: name 'st' is not defined`. Il faut un wrapper dont le corps **importe à l'intérieur** :

```python
import numpy as np
from pathlib import Path
from streamlit.testing.v1 import AppTest

from utils.VideoClasses import UploadedVideo


def _app():
    # Import DANS le corps : obligatoire pour AppTest.from_function.
    from components.VideoStatus import afficher_statut_video
    afficher_statut_video()


def _fausse_video(nom: str, duree: float) -> UploadedVideo:
    # UploadedVideo est frozen/slots : les 9 champs sont requis.
    # VideoStatus ne lit que name / duration / thumbnail ; le reste = valeurs bidon.
    return UploadedVideo(
        path=Path("/tmp/fake.mov"),
        name=nom,
        duration=duree,
        width=10,
        height=10,
        fps=30.0,
        size_bytes=123,
        file_id="test",
        thumbnail=np.zeros((10, 10, 3), dtype=np.uint8),  # frame RGB minimale
    )


def test_statut_sans_video_affiche_la_caption():
    at = AppTest.from_function(_app)
    at.run()
    assert not at.exception
    assert len(at.sidebar.success) == 0
    assert at.sidebar.caption[0].value == "Aucune vidéo chargée"


def test_statut_avec_video_masque_l_emoji():
    at = AppTest.from_function(_app)
    at.session_state["uploaded_video"] = _fausse_video("ma_video.mov", 12.0)
    at.run()

    assert not at.exception
    assert len(at.sidebar.success) == 1
    banniere = at.sidebar.success[0]

    # (b) Le 🎬 est rendu comme ICÔNE, pas dans le texte. On assert sur .icon.
    assert banniere.icon == ""            # ROUGE aujourd'hui (icon == "🎬")
    assert "ma_video.mov" in banniere.value
    assert "12" in banniere.value
```

**(b) Pourquoi `.icon` et pas `.value` ?** Parce que Streamlit sort l'emoji de tête dans `.icon`. Si tu assertais `"🎬" not in banniere.value`, le test serait **déjà vert** avec le code actuel (le texte ne contient jamais le 🎬) → il ne prouverait rien. `banniere.icon == ""` est **faux aujourd'hui** (l'icône vaut `"🎬"`) et deviendra vrai après la modif. C'est ça, un vrai rouge→vert.

### 4.4 Progression attendue

```bash
uv run pytest -v
```

- `test_statut_sans_video…` → **vert** (garde anti-régression).
- `test_dimensions…` → **vert** dès que le module §5.1 existe.
- `test_statut_avec_video_masque_l_emoji` → **ROUGE** (`icon == "🎬" != ""`) → passe au **vert** après la modif §5.3.

**Limite assumée :** AppTest **n'expose pas** `st.image` ni la largeur d'un média. Et `VideoToGifs.py` / `Home.py` exécutent leur logique **au niveau module** (avec `st.stop()` précoce, MoviePy et I/O disque) → non testables proprement sans une vraie vidéo de fixture. C'est un _smell_ de testabilité réel (logique de page hors fonction), **hors périmètre ici**. Conséquence : **les tailles (S1–S4) se vérifient à l'œil** (§7), pas en test automatique.

---

## 5. Modifications pas à pas

### 5.1 Nouveau module de constantes — `src/utils/Dimensions.py`

```python
"""Dimensions d'affichage des médias (en pixels)."""

# Aperçus (largeur fixe)
LARGEUR_APERCU_GIF = 480      # GIF généré (page Vidéo → GIF)
LARGEUR_APERCU_VIDEO = 480    # lecteur vidéo source (Accueil + Vidéo → GIF)

# Vignettes
LARGEUR_VIGNETTE_ACCUEIL = 140   # miniature du bloc « vidéo chargée »
LARGEUR_VIGNETTE_SIDEBAR = 56    # miniature dans la barre latérale
```

- **Nom du fichier** : `Dimensions.py` en PascalCase pour rester cohérent avec `VideoClasses.py` / `GifClasses.py` déjà présents dans `utils/`.
- **Valeurs** : ce sont des points de départ raisonnables (la zone centrale fait ~730 px). Ajuste-les à l'œil ensuite — c'est tout l'intérêt de les avoir regroupées ici.

### 5.2 Écris les tests (§4) et lance-les → tu dois voir le ROUGE sur `test_statut_avec_video_masque_l_emoji`.

### 5.3 `src/components/VideoStatus.py` — la vignette remplace le 🎬 (S5)

Bloc actuel (lignes 14–18) :

```python
    with st.sidebar:
        if video is not None:
            st.success(f"🎬 {video.name} · {video.duration:.0f} s")
        else:
            st.caption("Aucune vidéo chargée")
```

Cible (comprends chaque ligne, puis retape) :

```python
    with st.sidebar:
        if video is not None:
            col_vignette, col_infos = st.columns([1, 3], vertical_alignment="center")
            with col_vignette:
                st.image(video.thumbnail, width=LARGEUR_VIGNETTE_SIDEBAR)
            with col_infos:
                st.success(f"{video.name} · {video.duration:.0f} s")  # plus de 🎬
        else:
            st.caption("Aucune vidéo chargée")
```

Et l'import en tête de fichier :

```python
from utils.Dimensions import LARGEUR_VIGNETTE_SIDEBAR
```

**Points de vigilance :**

- **Pas de garde `if video.thumbnail is not None`.** Le champ `thumbnail` est **requis** dans `UploadedVideo` et toujours rempli par `clip.get_frame(0)` (`Home._build_uploaded_video`). Le cas `None` est **mort** ; une branche défensive non testée sur un cas impossible, c'est le contraire du TDD. On ne l'ajoute pas.
- **Ne teste jamais** `if video.thumbnail:` — un `ndarray` non scalaire lève `ValueError: truth value of an array … is ambiguous`. (Ici on n'en a pas besoin ; c'est juste le réflexe à ne pas avoir.)
- La branche `else` (sans vidéo) **ne change pas** : le test `test_statut_sans_video…` la protège.

➡️ Relance `uv run pytest -v` : tout doit être **vert**.

### 5.4 `src/pages/VideoToGifs.py` — aperçu GIF (S1), puis _spike_ mobile

Ligne 153, remplace :

```python
                st.image(octets)
```

par :

```python
                st.image(octets, width=LARGEUR_APERCU_GIF)
```

Import en tête :

```python
from utils.Dimensions import LARGEUR_APERCU_GIF, LARGEUR_APERCU_VIDEO
```

**➡️ STOP — fais le _spike_ maintenant** (avant les 3 autres sites). Lance l'app, charge une vidéo, génère un GIF, puis **rétrécis la fenêtre** à une largeur mobile (ou DevTools → device toolbar) :

- **Pas de barre de défilement horizontale** et le GIF tient dans l'écran → le clamp fonctionne, continue avec le px fixe pour S2/S3/S4.
- **Débordement** → adopte le **repli responsive** (encadré §6) pour S1, et applique-le aussi à S2/S3/S4.

Une fois le spike concluant, ligne 75 :

```python
st.video(str(current.path))                       # avant
st.video(str(current.path), width=LARGEUR_APERCU_VIDEO)   # après
```

### 5.5 `src/pages/Home.py` — vignette d'accueil (S3) + vidéo source (S4)

Ligne 134 :

```python
            st.image(current.thumbnail, width="stretch")     # avant
            st.image(current.thumbnail, width=LARGEUR_VIGNETTE_ACCUEIL)   # après
```

Ligne 152 :

```python
        st.video(str(current.path))                          # avant
        st.video(str(current.path), width=LARGEUR_APERCU_VIDEO)   # après
```

Import en tête :

```python
from utils.Dimensions import LARGEUR_APERCU_VIDEO, LARGEUR_VIGNETTE_ACCUEIL
```

**Pourquoi S3 était « trop grande » :** la vignette est déjà dans une colonne `[1, 3]` (donc ~1/4 de la largeur sur desktop). Son vrai problème est **le repliement des colonnes sur mobile** : Streamlit empile les colonnes → la vignette passe **pleine largeur**. Une largeur fixe (140 px) la garde petite même empilée. (Ce n'est donc pas un débordement desktop qu'on corrige, mais ce comportement mobile.)

---

## 6. Repli responsive (uniquement si le spike montre un débordement)

> Motif natif, sans CSS. Il borne **et** reste fluide des deux côtés. Valide pour `st.image` comme pour `st.video` (les deux acceptent `width="stretch"`).

```python
_, milieu, _ = st.columns([1, 2, 1])
with milieu:
    st.image(octets, width="stretch")   # ou st.video(..., width="stretch")
```

La colonne du milieu occupe la moitié centrale de la zone : le média y remplit un conteneur déjà borné (donc jamais géant sur desktop) et déjà responsive (donc jamais débordant sur mobile). Ajuste le ratio (`[1, 2, 1]`, `[1, 3, 1]`…) pour la taille voulue.

---

## 7. Vérification

**1. Tests automatiques :**

```bash
uv run pytest -v
```

Tout doit être **vert** (2 tests sidebar + 1 test dimensions).

**2. Contrôle visuel** (`uv run streamlit run App.py`) — charge idéalement une vidéo **portrait** :

- [ ] **Sidebar** (sur les 2 pages) : petite vignette **à gauche** du bandeau vert, **plus de 🎬**.
- [ ] **Accueil** : vignette du bloc « vidéo chargée » plus petite ; lecteur vidéo source borné.
- [ ] **Vidéo → GIF** : lecteur vidéo source borné ; GIF généré borné.
- [ ] **Mobile (bloquant)** : rétrécis la fenêtre / device toolbar → **aucun défilement horizontal**, chaque média tient dans l'écran, le portrait n'occupe pas toute la hauteur. Si un site déborde → repli §6.

---

## Bonnes pratiques appliquées

- **Tests d'abord** — vrai rouge→vert sur `VideoStatus` via `.icon` ; les tailles (S1–S4) sont vérifiées **manuellement**, faute d'observable côté AppTest et à cause de la logique de page au niveau module (_smell_ nommé, hors périmètre).
- **Gestion d'erreurs / cas limites** — pas de garde morte sur `thumbnail` (champ requis, toujours rempli) ; le portrait est borné en hauteur par la largeur (ratio conservé) ; l'upscaling d'un petit GIF est accepté et documenté.
- **Validation des entrées** — les champs affichés proviennent d'un `UploadedVideo` construit **après** ouverture réussie par MoviePy ; on ne s'appuie pas sur le filtre d'upload. _(Aparté hors périmètre : `st.file_uploader(type="video/_")`dans`Home.py:51`est vraisemblablement un filtre inopérant —`type`attend des extensions comme`["mov", "mp4"]`. À traiter séparément si tu veux.)\*
- **Structure du code** — un module partagé `utils/Dimensions.py` (4 valeurs / 3 fichiers) ; chaque site importe la constante qui le concerne.
- **Sécurité** — rendu natif (`bytes` / `ndarray`), aucune surface d'injection HTML/markdown, aucun secret. Rien à exploiter — et cohérent avec ta préférence « natif only ».
- **Idiomes** — chaînes et commentaires en français ; widgets natifs uniquement ; API `width` courante (pas de `use_column_width` déprécié) ; type hints conservés ; noms de fichiers en PascalCase comme les `utils/` existants.

---

_Quand tu as écrit le code, dis-le moi : je relis volontiers ta version._
