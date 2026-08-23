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
*exacte* (err 0,00) là où la globale plafonne à 1,12. C'est structurel, pas un
défaut d'échantillonnage — chaque image prise isolément tient sous 256
couleurs, mais leur **union** sur 50 images les dépasse. Vérifié : passer de 8 à
50 images d'analyse ne bouge pas l'erreur d'un centième.

### D2 — Quantificateur MAXCOVERAGE

Trois candidats, mesurés avec `kmeans=1` (cf. D5) sur quatre contenus :

| | MEDIANCUT | **MAXCOVERAGE** | FASTOCTREE |
|---|---|---|---|
| vidéo réelle | 10,59 Mo · err 2,89 | **9,53 Mo** · err 3,10 | 9,44 Mo · err 3,40 |
| `degrade` | 3,38 Mo · err 0,99 | **3,35 Mo · err 0,88** | 3,57 Mo · err 3,38 |
| `camera` | 5,49 Mo · err 1,25 | **3,85 Mo** · err 1,48 | — |
| `ecran` | 0,03 Mo · err 1,12 | identique | identique |

MEDIANCUT concentre ses entrées là où les pixels sont denses, ce qui minimise
l'erreur mais maximise l'entropie de la carte d'index. MAXCOVERAGE les répartit
pour **couvrir** l'espace des couleurs : les entrées étant plus écartées,
davantage de pixels voisins tombent sur la même, ce qui allonge les suites
d'index identiques — la seule chose que LZW sache compresser. Le gain est de
10 % sur du photographique, 30 % sur du bruité, et l'erreur baisse même sur les
dégradés.

FASTOCTREE reste écarté : plus léger encore, mais il n'alloue que ~109 couleurs
sur 256 sur un dégradé continu et y produit des bandes visibles.

Une variante « palette étirée en contraste » (entrées écartées du gris moyen
après coup) a été mesurée et **rejetée** : très efficace sur le poids (−37 % sur
`degrade`, −78 % sur `camera`) mais elle fausse les couleurs dès que le contenu
est plat — sur `ecran` elle rend +75 % de saturation par rapport à la source.
C'est un parti-pris esthétique, pas une optimisation.

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

### D4 — Analyse plafonnée à 240 px

Deux rôles, et le second est devenu le plus contraignant.

**Invariant mémoire** : analyser impose de tenir des images RGB à 3 octets par
pixel, quand la quantification travaille en mode « P » à 1 octet. Le pic
d'analyse reste constant quelle que soit la résolution de la source.

**Coût de l'affinage** : k-moyennes (D5) tourne sur le montage, donc son temps
suit la surface. Mesuré sur la vidéo réelle, montage de 16 images :

| largeur d'analyse | surface | temps palette | poids | saturation |
|---|---:|---:|---:|---:|
| 480 px | 2,07 Mpx | 10,81 s | 5,53 Mo | −0,8 % |
| **240 px** | 0,52 Mpx | **2,68 s** | **5,44 Mo** | **−0,4 %** |
| 160 px | 0,23 Mpx | 1,28 s | 5,44 Mo | −0,4 % |

La palette n'y perd rien, et gagne même un peu. Le montage n'a pas à être
fidèle, il doit être **représentatif** : un sous-échantillonnage d'un pixel sur
quatre l'est autant que l'image entière. 160 px conviendrait aussi ; 240 px est
retenu comme marge de sûreté sur des contenus à détails fins.

### D5 — Affinage k-moyennes, et sous-échantillonnage sans moyennage

Ajouté après constat sur média réel : les couleurs sortaient ternes. Cause
racine mesurée, deux contributeurs, aucun lié au décodage (vérifié : MoviePy
0,2878 contre ffmpeg 0,2942, et forcer la plage complète ne change rien).

**MEDIANCUT retient la MOYENNE de chacune de ses 256 boîtes.** Une moyenne est
tirée vers le centre : aucune entrée n'atteint les couleurs les plus saturées ni
les extrêmes de luminance. Sur une vidéo de vigne, la palette était bornée à
[6, 250] quand la source va de 0 à 255. `kmeans=1` corrige — au-delà de 1,
Pillow ne bouge plus, c'est un interrupteur et non un compteur d'itérations.

**La réduction BOX des images d'analyse rétrécissait le gamut avant même la
quantification** : moyenner un pixel saturé avec son voisin plus terne fait
disparaître l'extrême de l'échantillon. `NEAREST` prélève sans calculer, donc
chaque couleur du montage existe réellement dans la source.

| Sur la vidéo réelle | saturation | écart | poids |
|---|---:|---:|---:|
| BOX, `kmeans=0` (avant) | −2,8 % | 3,27 | 10,81 Mo |
| BOX, `kmeans=1` | −0,9 % | 2,90 | 10,62 Mo |
| NEAREST, `kmeans=0` | −2,1 % | 3,24 | 10,80 Mo |
| **NEAREST, `kmeans=1`** | **−0,5 %** | **2,89** | **10,59 Mo** |

Coût : la palette passe de 0,16 s à 1,25 s. Accepté explicitement — du temps
d'export contre de la qualité et du poids.

**Leçon de méthode** : l'écart absolu moyen, seule métrique de la §2, est
AVEUGLE à ce défaut. Tirer chaque couleur de 3 % vers le gris produit une erreur
moyenne minuscule et une image visiblement terne. C'est pourquoi D4 avait validé
la réduction BOX à tort. Toute évaluation de quantification doit désormais
mesurer la **saturation** en plus de l'écart.

Écarté au passage : supprimer le plafond `LARGEUR_ANALYSE` gagnerait 0,2 point
de saturation de plus, contre ~200 Mo de pic mémoire transitoire sur du 1080p.

### D6 — `palette=` passé explicitement à `save()`

Dans `GifImagePlugin._write_multiple_frames` :

```python
else:
    # compress difference
    if not palette:
        frame_data.encoderinfo["include_color_table"] = True
```

Sans `palette=`, Pillow écrit une table de couleurs **par image delta** sans
voir qu'elles partagent déjà la même. Mesuré : 49 tables locales écrites pour
rien, à couleur rigoureusement identique — 3 à 13 % du fichier selon le contenu.

L'argument est donc **obligatoire**, pas une redondance de confort : c'est lui
qui fait exister la palette globale dans le fichier produit, pas seulement dans
le code qui le produit.

### D7 — Le curseur porte sur la largeur de sortie, en pixels

Le format n'offre aucune compression exploitable sur du contenu photographique.
Mesuré sur la vidéo réelle : la carte d'index porte **7,89 bits d'entropie sur 8
possibles**, 82 % des pixels diffèrent de leur voisin horizontal, 88 % changent
d'une image à l'autre. Le plancher théorique au premier ordre est de 11,36 Mo et
nous sortions à 10,59 — donc **déjà sous ce plancher**. Aucune astuce d'encodage
ne reste disponible, ce que confirme la comparaison : au format identique,
ffmpeg `palettegen` / `paletteuse` sort à 5,82 Mo là où nous sortons à 5,44.

Le poids suit donc le nombre de pixels de façon quasi linéaire, et c'est le seul
levier qui ne coûte **aucune** couleur :

| curseur | sortie | poids | octet/pixel | écart |
|---|---|---:|---:|---:|
| 160 px | 160×90 | 0,66 Mo | 0,92 | 3,1 |
| 240 px | 240×135 | 1,43 Mo | 0,89 | 3,1 |
| 320 px | 320×180 | 2,48 Mo | 0,86 | 3,1 |
| 400 px | 400×225 | 3,83 Mo | 0,85 | 3,1 |
| 480 px | 480×270 | 5,44 Mo | 0,84 | 3,1 |

Le coût par pixel ne bouge pas, et l'écart de couleur non plus. D'où le modèle
que la page peut annoncer sans encoder :

**poids ≈ largeur × hauteur × nombre d'images × 0,85 octet**

**Des pixels et non un pourcentage.** L'ancien curseur « Échelle » exprimait une
fraction de la source, ce qui posait deux problèmes : il se lisait différemment
selon la vidéo importée, et surtout il créait une **zone morte** dès que la
source dépassait le plafond — sur une source 1080p, il ne produisait aucun effet
de 100 % à 25 %. Le curseur « Largeur » nomme exactement ce qu'il produit, et
chacune de ses positions donne des dimensions distinctes, quelle que soit la
source (vérifié sur 640 px et 1920 px).

`largeurs_disponibles(largeur_source)` plafonne le catalogue par la source,
exactement comme `GifQuality.vitesses_disponibles` le fait par la cadence : on
ne propose jamais d'agrandir. La largeur maximale atteignable y figure toujours,
même hors catalogue — une source de 300 px doit pouvoir sortir en 300 px.

`ConversionParams.dimensions_sortie` reste la source unique des dimensions :
l'export s'en sert pour redimensionner, le panneau pour son alerte mémoire, la
page pour annoncer la taille avant le clic.

### D8 — Rejetés après mesure

- `optimize=True` à l'écriture : gain nul sur les trois contenus.
- Augmenter le nombre d'images d'analyse au-delà de 16 : n'améliore pas
  l'erreur (cf. D1).
- Tramage Bayer : pertinent seulement si l'on réintroduit un jour du tramage.
  Retenir alors Bayer et non Floyd-Steinberg — motif périodique donc
  compressible : +0,01 Mo contre +0,58 Mo sur `ecran`.
- `optimize=True` **avec un index de transparence libre** (palette à 255
  couleurs au lieu de 256, ce qui laisse Pillow remplir de transparent les
  pixels inchangés) : hypothèse formée d'après le code de
  `_write_multiple_frames`, mesurée, **fausse ici** — 10,56 Mo contre 10,59. Le
  delta transparent ne paie que si des pixels sont identiques d'une image à
  l'autre, or 88 % changent sur du contenu filmé à main levée.
- Lissage spatial avant quantification : l'erreur explose (2,89 → 13,05 pour
  −21 % de poids). Mauvais échange.
- Débruitage temporel `hqdn3d` : efficace sur une source fixe, inopérant ici —
  la caméra bouge.

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
quantifie en `MEDIANCUT`, `COULEURS_GIF` couleurs.

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
3. **Assemblage** — `images[0].save(...)` **sans `disposal=2`** et **avec
   `palette=`** (cf. D6). `duration`, `loop=0` et `save_all` inchangés.

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

## 6. Résultat obtenu

Relevé via `convertir_en_gif`, segment de 5 s à 10 i/s, échelle demandée 100 % :

| | Avant (code d'origine) | Après |
|---|---|---|
| **vidéo réelle** 640×360 | 5,54 Mo · err 14,58 | **5,44 Mo · err 3,13** en 480×270 |
| `ecran` 1280×720 | 2,14 Mo · err 16,88 | **0,03 Mo** en 480×270 |
| `degrade` 1280×720 | 4,54 Mo · err 16,50 | **2,04 Mo · err 1,15** |
| `camera` 1280×720 | 2,15 Mo · err 4,30 | **1,49 Mo · err 1,51** |

Plus léger **et** plus fidèle sur les quatre contenus. Sur la vidéo réelle, le
poids est celui de l'origine avec un écart de couleur 4,7 fois moindre.

Durée d'export sur la vidéo réelle : 3,0 s, dont 2,7 s d'affinage de palette.

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
