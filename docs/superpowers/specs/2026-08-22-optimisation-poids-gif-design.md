# Optimisation du poids des GIFs — design

Date : 2026-08-22
Statut : validé, prêt pour plan d'implémentation
Portée : `src/utils/GifExport.py`, `src/utils/GifPalette.py` (nouveau), `src/components/GifPanel.py`

## 1. Le problème

Les GIFs produits sont anormalement lourds. Mesuré sur trois contenus de
référence, segment de 5 s, 1280×720 réduit à 640×360 à 10 i/s (50 images) :

| Source | Poids source | GIF produit |
|---|---:|---:|
| `ecran` (aplats, capture d'écran) | 18 Ko | **2,14 Mo** |
| `degrade` (dégradé continu) | 694 Ko | **4,54 Mo** |
| `camera` (photographique bruité) | 11,1 Mo | 2,15 Mo |

Une source de 18 Ko produit un GIF de 2,14 Mo. Ce n'est pas le prix du format.

## 2. Diagnostic

### 2.1 La cause principale : un tramage non voulu

`GifExport._quantifier` appelle `Image.fromarray(frame).convert("P")` avec ses
arguments de palette commentés. Sans `palette=ADAPTIVE`, Pillow applique deux
choses par défaut, aucune des deux souhaitée :

- la palette **WEB** — 216 couleurs sur un cube 6×6×6, qui ne contient
  pratiquement aucune couleur réelle d'une vidéo ;
- le tramage **Floyd-Steinberg**, qui *simule* les couleurs absentes en semant
  du bruit d'erreur.

LZW, seul mécanisme de compression du format GIF, ne compresse que des suites
de pixels d'index identiques. Le tramage les détruit toutes. Mesuré sur une
image de `ecran`, taux de transitions horizontales entre pixels voisins :

| | couleurs | transitions |
|---|---:|---:|
| `convert("P")` — code actuel | 22 | **91,6 %** |
| `convert("P", dither=NONE)` | 5 | 0,3 % |
| `convert("P", palette=ADAPTIVE)` | 62 | 1,1 % |

Le tramage coûte donc doublement : il gonfle le fichier **et** il déplace la
couleur. Écart colorimétrique moyen (erreur absolue par canal, échelle 0–255)
entre le GIF et la source :

| | Code actuel | Palette adaptative |
|---|---|---|
| `ecran` | 2,14 Mo · err **16,88** | 0,06 Mo · err **0,00** |
| `degrade` | 4,54 Mo · err **16,50** | 3,73 Mo · err 0,54 |
| `camera` | 2,15 Mo · err 4,30 | 11,89 Mo · err 1,48 |

Sur du contenu graphique, le code actuel est **dominé sur les deux axes à la
fois** : 36× plus lourd et 17 niveaux d'écart de couleur.

La ligne commentée n'était donc pas la cause de la dégradation perçue — c'est
exactement ce que faisait MoviePy : `write_gif` → `imageio` →
`Pillow.GifImagePlugin._normalize_mode`, qui exécute littéralement
`im.convert("P", palette=Image.Palette.ADAPTIVE)`. La dégradation perçue à
l'époque venait vraisemblablement du **scintillement de palette** : une palette
recalculée par image fait pulser légèrement l'ensemble d'une image à l'autre.
La palette globale retenue ici supprime ce phénomène par construction.

### 2.2 La cause secondaire : `disposal=2`

`disposal=2` demande à chaque image d'effacer la précédente. Pillow ne peut
alors plus n'encoder que le rectangle modifié et réécrit chaque image en
entier. Le gain de son retrait est massif sur du contenu à fond fixe et nul sur
du contenu qui bouge partout — ce qui est cohérent : le delta ne paie que
lorsque des pixels sont identiques d'une image à l'autre.

| | `disposal=2` | sans `disposal` |
|---|---:|---:|
| `ecran` | 0,17 Mo | **0,06 Mo** |
| `degrade` | 3,72 Mo | 3,73 Mo |
| `camera` | 11,81 Mo | 11,89 Mo |

Le commentaire qui justifie `disposal=2` (« évite les traînées si les palettes
diffèrent ») cesse de s'appliquer dès lors qu'une palette **unique** sert tout
le GIF : les palettes ne diffèrent plus jamais. La palette globale supprime la
raison d'être de `disposal=2`.

### 2.3 Cadrage : GIF contre vidéo

Réencodage de chaque source en H.264 aux dimensions et au nombre d'images
exacts du GIF, pour comparer à réglages égaux :

| | MP4 640×360, 50 images | Meilleur GIF, mêmes réglages |
|---|---:|---:|
| `ecran` | 6,6 Ko | 40 Ko (**×6**) |
| `degrade` | 117 Ko | 3 500 Ko (**×30**) |
| `camera` | 555 Ko | 6 100 Ko (**×11**) |

Réduire les dimensions et le nombre d'images reste un levier réel. Mais le
format lui-même coûte 6 à 30× le prix de H.264 : quand un GIF finit plus léger
que sa source, c'est parce qu'on a jeté les données d'entrée avant. Ce ratio
fixe le plancher atteignable ; il ne change pas ce qu'il faut faire.

## 3. Décisions de conception

### D1 — Palette globale unique, toujours

Une seule palette pour tout le GIF, sans exception et sans arbitrage à
l'exécution.

Une variante sondant le contenu pour choisir entre palette locale et globale a
été conçue, mesurée et **rejetée** : elle produisait un GIF lourd dans un cas
et léger dans un autre sans que l'utilisateur puisse comprendre pourquoi. La
prévisibilité prime sur le gain marginal.

Conséquence assumée : sur du contenu à aplats, la palette locale était
*exacte* (err 0,00) là où la globale plafonne à ~0,84. C'est structurel, pas un
défaut d'échantillonnage — chaque image prise isolément tient sous 256
couleurs, mais leur **union** sur 50 images les dépasse. Vérifié : passer de 8 à
50 images d'analyse ne bouge pas l'erreur d'un centième.

### D2 — Quantificateur FASTOCTREE

| | Code actuel | MEDIANCUT | **FASTOCTREE** |
|---|---|---|---|
| `ecran` | 2,14 Mo · err 16,88 | 0,04 Mo · err 1,12 | **0,03 Mo · err 0,84** |
| `degrade` | 4,54 Mo · err 16,50 | 3,55 Mo · err 1,13 | **2,16 Mo** · err 1,50 |
| `camera` | 2,15 Mo · err 4,30 | 6,02 Mo · err 1,62 | **1,49 Mo** · err 1,72 |

FASTOCTREE est le seul des deux qui améliore poids **et** fidélité par rapport
au code actuel sur les trois contenus. Les cellules de l'octree s'alignent sur
les bits de poids fort : des pixels voisins légèrement différents tombent dans
la même cellule, donc reçoivent le même index — précisément ce que LZW
compresse. Il construit aussi la palette environ 10× plus vite.

MEDIANCUT a été écarté malgré sa meilleure fidélité sur les dégradés (1,13
contre 1,50) parce qu'il rend le contenu photographique bruité **2,8× plus
lourd qu'aujourd'hui** — le symptôme même que ce travail corrige.

Faiblesse connue et acceptée : sur un dégradé continu, FASTOCTREE n'alloue que
~109 couleurs sur 256 et produit un banding visible. Le corpus de mesure est
synthétique (`gradients` et `testsrc2` de ffmpeg) ; `degrade` est un pire cas
que peu de vraies sources atteignent. **À rejouer sur un média réel** si un
banding est constaté en usage.

### D3 — Images d'analyse : 16, uniformément réparties, par seeks

Réparties sur toute la durée du segment, jamais les *n* premières : une palette
calée sur le début du plan trahirait tout changement de lumière ou de cadrage.

Récupérées par `get_frame` à 16 instants calculés, et non par un décodage
linéaire complet. La raison n'est pas le gain brut mais le **coût constant** :

Mesuré sur `degrade` puis `camera`, segment de 5 s :

| | 50 images | 100 images |
|---|---:|---:|
| Décodage linéaire | 0,37 / 0,43 s | 0,62 / 0,68 s |
| 16 seeks | 0,21 / 0,31 s | **0,21 / 0,30 s** |

Le linéaire suit la longueur du segment ; les seeks non. Sur un segment de 30 s
à 20 i/s le linéaire coûterait ~4 s, les seeks toujours 0,2 à 0,3 s.

### D4 — Analyse plafonnée à 480 px

Les images d'analyse sont réduites à 480 px de large au plus. Vérifié : la
palette construite sur des images réduites vaut celle construite en plein
format (`camera` 6,01 Mo / err 1,65 contre 6,12 / 1,53 ; `degrade` 3,53 / 0,84
contre 3,55 / 1,02 — donc parfois meilleure).

L'enjeu est un **invariant mémoire** : sonder impose de tenir des images RGB, à
3 octets par pixel, alors que la passe de quantification travaille en mode « P »
à 1 octet. Sans plafond, 16 images de 1080p pèseraient 150 Mo et annuleraient
le gain revendiqué par l'en-tête de `GifExport`. Avec plafond, le pic d'analyse
est d'environ 13 Mo (images + montage), **constant quelle que soit la source**.

### D5 — Rejetés après mesure

- `optimize=True` à l'écriture : gain nul sur les trois contenus.
- Augmenter le nombre d'images d'analyse au-delà de 16 : n'améliore pas
  l'erreur (cf. D1).
- Tramage Bayer : pertinent seulement si l'on réintroduit un jour du tramage.
  Retenir alors Bayer et non Floyd-Steinberg — motif périodique donc
  compressible : +0,01 Mo contre +0,58 Mo sur `ecran`.

## 4. Architecture

### 4.1 Nouveau module `src/utils/GifPalette.py`

Couche pure : PIL et numpy uniquement, ni Streamlit ni MoviePy — même contrat
que `utils.Layout` et `utils.PreviewGif`.

```python
COULEURS_GIF = 256        # plafond du format ; déménage depuis GifExport
IMAGES_ANALYSE = 16
LARGEUR_ANALYSE = 480

def instants_analyse(duree: float, fps: int, nb: int = IMAGES_ANALYSE) -> list[float]
def construire_palette(echantillon: Sequence[Image.Image]) -> Image.Image
def appliquer_palette(image: Image.Image, palette: Image.Image) -> Image.Image
```

`instants_analyse` est de l'arithmétique pure, donc éprouvable sans média :
instants uniformément répartis sur `[0, duree - 1/fps]`, **dédoublonnés sur
l'indice d'image** pour qu'un segment plus court que 16 images ne demande jamais
deux fois la même. La borne haute reprend la doctrine déjà posée par
`PreviewGif.temps_vignette` : demander une image exactement à `t == duree` fait
lire ffmpeg au-delà de la dernière.

`construire_palette` empile l'échantillon en un montage vertical et le
quantifie en `FASTOCTREE`, `COULEURS_GIF` couleurs.

`appliquer_palette` fait `image.quantize(palette=..., dither=Dither.NONE)`.
`dither=NONE` est explicite et non implicite : c'est la valeur dont dépend tout
le gain de poids, elle ne doit pas pouvoir se perdre dans un défaut de
bibliothèque.

### 4.2 `GifExport.convertir_en_gif` en deux passes

Signature et contrat de propriété du fichier de sortie **inchangés**.

1. **Analyse** — `segment.get_frame(t)` pour chaque `t` de `instants_analyse`,
   chaque image réduite à `LARGEUR_ANALYSE`, puis `construire_palette`.
   Coût mesuré 0,2 à 0,3 s, constant (cf. D3).
2. **Quantification** — inchangée dans son principe : en flux, une image à la
   fois, `appliquer_palette`, progression rapportée par image. C'est ce que la
   double passe sert à préserver.
3. **Assemblage** — `images[0].save(...)` **sans `disposal=2`**. `duration`,
   `loop=0` et `save_all` inchangés.

Ordre impératif : le garde-fou `a_produire < 1` reste **avant** la passe
d'analyse, pour qu'un segment dégénéré échoue avant tout travail.

### 4.3 Progression

Le callback passe de `(index, total)` à `(phase, index, total)` :

```python
class Phase(StrEnum):
    ANALYSE = "analyse"
    QUANTIFICATION = "quantification"
    ASSEMBLAGE = "assemblage"
```

`GifPanel._generer` traduit la phase en libellé : « Analyse des couleurs —
4 sur 16 », « Image 12 sur 50 », « Assemblage du GIF… ». C'est le seul point
d'UI touché, et la progression y gagne en finesse — elle ne régresse pas.

## 5. Ce qui ne change pas

- Propriété de `chemin_sortie` et effacement sur `BaseException`.
- Validations : source absente, `end_time` hors durée, segment trop court.
- Post-condition `_relire_nb_images` : le fichier produit **est** un GIF.
- `fps` diviseur de 100 (`utils.GifQuality`), donc `duration` multiple de 10 ms.
- Pic mémoire de la quantification à 1 octet par pixel.
- `SEUIL_ALERTE_PIXELS` dans `GifPanel` : toujours valide.
- Aucune évolution de `ConversionParams` : l'incrément n'ajoute aucun réglage.

## 6. Résultat attendu

| | Avant | Après |
|---|---|---|
| `ecran` | 2,14 Mo · err 16,88 | **0,03 Mo · err 0,84** (÷71) |
| `degrade` | 4,54 Mo · err 16,50 | **2,16 Mo · err 1,50** (÷2,1) |
| `camera` | 2,15 Mo · err 4,30 | **1,49 Mo · err 1,72** (÷1,4) |

Plus léger et plus fidèle sur les trois contenus.

## 7. Vérification

**Les tests sont explicitement différés** : ils seront écrits séparément. Ce
qu'ils devront établir est consigné ici pour que le contrat ne se perde pas —
`GifExport` n'a aujourd'hui aucun test.

- **Fidélité sur aplat uni** : `fabrique_clip` du `conftest` produit déjà un mp4
  de couleur unie ; le GIF redécodé doit rendre cette couleur. C'est le test que
  le code actuel échoue — le bug écrit sous forme d'assertion.
- **Absence de traînée** : un carré en déplacement, GIF redécodé image par
  image et comparé aux images attendues. C'est ce test qui justifie le retrait
  de `disposal=2` autrement que par le raisonnement de la §2.2. Demande un
  fixture `fabrique_clip_anime` aux côtés de `fabrique_clip`.
- **Plafond de poids** sur l'aplat uni : verrou contre le retour d'un tramage.
- **`instants_analyse`** : répartition uniforme, borne haute à `duree - 1/fps`,
  dédoublonnage quand le segment compte moins de 16 images.
- Comportements existants non couverts : source absente, `end_time` hors durée,
  segment trop court, effacement du fichier sur échec, relecture de `n_frames`.

## 8. Hors périmètre

Consigné comme suite explicite, pas comme oubli.

- **Leviers avec perte, sous commande explicite** : débruitage **temporel**
  (mesuré `camera` 5,14 → 1,65 Mo, ×3,1 — de loin le plus puissant sur du
  photographique, parce qu'il rend les images voisines identiques et réalimente
  le delta), réduction de palette (256 → 32 : ×1,4), tramage Bayer.
- **Estimateur de poids avant le clic** (`IDEATION_GIF.md:65`). Les mesures
  ci-dessus montrent un facteur 100 de poids entre contenus à réglages
  identiques : une estimation honnête devra sonder le média, pas appliquer une
  formule.
- **`gifsicle`** en post-traitement : écarté, dépendance binaire externe.
- **Sorties WebP / MP4** (`IDEATION_GIF.md:39`).
