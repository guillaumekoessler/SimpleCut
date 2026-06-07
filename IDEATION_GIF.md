# Roadmap fonctionnelle — Application Streamlit d'édition de GIF

> Document de cadrage produit pour une application Streamlit **spécialisée dans l'édition de GIF en local**, basée sur MoviePy et augmentée par des modèles d'IA légers. Positionnement : combler le vide entre les éditeurs web limités (Ezgif, GIPHY tools) et les outils lourds desktop (Photoshop, After Effects).

---

## Préambule — Pourquoi un outil dédié au GIF ?

### Le créneau actuel

L'édition GIF souffre d'un paradoxe : c'est un format omniprésent (Slack, Discord, GitHub, Reddit, Tenor, messageries) mais aucun outil moderne ne lui est pleinement dédié. Les solutions existantes :

- **Ezgif** : web, gratuit, mais limité en taille (50 Mo), confidentialité douteuse (upload externe), UX datée.
- **GIPHY tools** : cloud-only, écosystème fermé, peu de contrôle technique.
- **Photoshop / After Effects** : coûteux, lourds, courbe d'apprentissage élevée pour une tâche aussi spécifique.
- **Gifski, gifsicle** : excellents mais CLI, inaccessibles au grand public.

Un outil **Streamlit local** apporte trois avantages décisifs : **confidentialité** (les GIFs ne quittent pas la machine), **pas de limite de taille**, **itération instantanée** sur de petits fichiers (un GIF de 2 Mo est traité en quelques secondes).

### Spécificités techniques du GIF à intégrer dans toute l'app

Le GIF n'est pas une "vidéo courte" : c'est un format à part avec ses propres contraintes, que toute l'UI doit refléter.

- **Palette limitée à 256 couleurs par frame** (format GIF89a). Conséquence : la qualité visuelle dépend autant de la quantification de palette que de la résolution. Tout export GIF doit exposer un contrôle de palette.
- **Alpha binaire uniquement** : transparent ou opaque, pas de demi-transparence. Tout matting / détourage doit prévoir un seuillage et un lissage morphologique des bords.
- **Pas d'audio** : tout le tier audio de l'application générale devient obsolète. Les pages adaptées se concentrent sur le visuel pur.
- **Conception pour la boucle** : la qualité d'un GIF tient souvent à la fluidité de sa boucle. `MakeLoopable`, détection automatique de point de boucle, et `TimeSymmetrize` sont centraux.
- **Frame rate typiquement bas** (10–20 fps) : les effets de vitesse, slow-mo et interpolation deviennent plus délicats — il y a peu de matière brute.
- **Durée courte** (2–10s typique) : le découpage doit être **frame-precise** et non pas en secondes approximatives. Chaque frame compte.
- **Poids dominé par** : dimensions × nombre de frames × richesse de la palette. Les leviers d'optimisation sont donc multiples.
- **Loop count** : un GIF peut boucler à l'infini, N fois, ou une seule fois. Souvent oublié dans les outils basiques.
- **Disposal method** : comment chaque frame s'efface — `background`, `none`, `previous`. Important pour les GIFs avec transparence.

### Stack architecturale recommandée

- **Backbone** : MoviePy 2.x (lecture/écriture GIF, effets, composition).
- **Optimisation palette** : `pillow` pour la quantification, `gifsicle` (binaire CLI) en post-traitement pour la compression lossy.
- **Modèles IA légers privilégiés** : ONNX runtime (CPU), MediaPipe, faster-whisper-style — pour rester déployable sans GPU.
- **Format de sortie multiple** : GIF natif, mais aussi WebP animé (meilleur compromis poids/qualité, supporté nativement par navigateurs modernes), APNG (qualité parfaite, alpha continu), et MP4 (le plus léger en réalité).
- **Streamlit multipage** avec `session_state` typé : l'objet `Gif` courant (chemin temp, métadonnées, pile d'opérations) est partagé entre toutes les pages.

---

# 🟢 Tier 1 — MVP indispensables pour l'édition GIF

## 1. Convertisseur Vidéo → GIF (la porte d'entrée)

**Description.** Génération de GIFs optimisés à partir d'une portion de vidéo source. C'est la fonctionnalité fondatrice et probablement la page la plus utilisée de toute l'application.

**Cas d'usage GIF.**

- Démontrer un bug dans une issue GitHub.
- Extraire un moment iconique d'un film / série pour réaction Discord.
- Créer un GIF de produit pour une landing page (poids critique).
- Transformer un screencast court en illustration de documentation.

**Fonctions MoviePy.** `VideoFileClip(path)`, `clip.subclipped(t1, t2)`, `vfx.Resize(width=...)`, `clip.with_fps(fps)`, `clip.write_gif(out, fps=15, program="ffmpeg")`.

**UI Streamlit.**

- Upload vidéo source (mp4, mov, avi, webm, mkv).
- Slider double pour bornes temporelles (avec affichage frame de début/fin en vignette).
- Slider FPS de sortie (5–30, défaut 15) — levier de poids n°1.
- Slider largeur de sortie (presets 240 / 320 / 480 / 640 / 720 px).
- **Estimateur de poids en temps réel** : `width × height × fps × duration × ratio_compression` — UX déterminante pour éviter les exports inutiles, à afficher en gros au-dessus du bouton d'export.
- Option "boucle douce" (auto-apply `vfx.AccelDecel` pour ramping).
- Option "boomerang" (auto-apply `vfx.TimeSymmetrize`).
- Choix backend : `ffmpeg` (rapide, bon par défaut) ou `imageio` (palette plus fine).

**Pièges GIF.**

- Au-delà de 10 Mo, le GIF devient inutilisable pour la plupart des plateformes : afficher un warning rouge.
- Le `fps` du GIF doit idéalement être un diviseur du fps source (15 depuis 30, 12 depuis 24) pour éviter le tearing temporel.
- Palette : un GIF très coloré (paysage, gradient) souffrira plus qu'un GIF graphique (UI, dessin).
- L'export GIF est mono-thread et lent : barre de progression obligatoire avec ETA.

**Extensions.** Post-traitement automatique via `gifsicle --optimize=3 --lossy=80` (gain ~30 % de poids sans perte visible), export simultané en WebP animé pour proposer un fallback moderne, prévisualisation du GIF directement dans le navigateur via `st.image`.

---

## 2. Convertisseur GIF → Vidéo (MP4 / WebM / WebP animé)

**Description.** Convertit un GIF existant vers des formats modernes (MP4 H.264, WebM VP9, WebP animé) qui pèsent 5 à 20 fois moins lourd pour une qualité supérieure. Utile quand on a hérité d'un GIF qu'on veut intégrer ailleurs (site web, réseaux sociaux qui acceptent désormais MP4).

**Cas d'usage GIF.**

- Réduire un GIF de 8 Mo en MP4 de 400 Ko pour intégration web.
- Convertir des GIFs historiques d'une base documentaire vers un format pérenne.
- Préparer un GIF pour Twitter/X qui accepte mieux les MP4.

**Fonctions MoviePy.** `VideoFileClip("input.gif")`, `clip.write_videofile(out, codec="libx264", audio_codec=None)` (pas d'audio dans le GIF source).

**UI Streamlit.**

- Upload GIF + métadonnées (nb frames, fps, dimensions, palette, poids).
- Choix format cible : MP4 H.264, MP4 H.265 (HEVC), WebM VP9, WebM AV1, WebP animé, APNG.
- Pour MP4 : choix CRF (qualité constante 18–28) + preset (ultrafast → veryslow).
- Pour WebP : choix qualité (0–100) + méthode (0–6, plus lent = mieux).
- Comparatif de poids estimé avant export (tableau formats).
- Aperçu côte-à-côte GIF original vs version convertie (sur frame fixe puis lecture).

**Pièges GIF.**

- Les MP4 ne supportent pas la transparence : warning si le GIF a un fond transparent → proposer WebP ou APNG à la place.
- L'encodage VP9 / AV1 est très lent : prévenir.
- Certaines plateformes n'autorisent pas tous les formats : tableau récapitulatif "supporté sur X / Y / Z".

**Extensions.** Mode batch (un dossier entier de GIFs vers MP4), génération d'un `<video>` HTML snippet prêt à intégrer (avec fallback `<img src="gif">`), export en sprite sheet pour usage CSS.

---

## 3. Trim frame-precise

**Description.** Découpe un GIF avec une précision **à la frame**, et non pas seulement en secondes. Sur un GIF de 60 frames à 15 fps, chaque frame représente 66 ms — la précision frame est indispensable.

**Cas d'usage GIF.**

- Retirer une ou deux frames parasites au début ou à la fin.
- Isoler la phase exacte d'un mouvement (le sourire, le clin d'œil, l'impact).
- Préparer un GIF avant raccordement seamless (page 12).

**Fonctions MoviePy.** `VideoFileClip("input.gif")`, accès au nombre de frames via `int(clip.duration * clip.fps)`, `clip.subclipped(frame_start/fps, frame_end/fps)`, ou `clip.with_subclip` selon le besoin.

**UI Streamlit.**

- Affichage du nombre total de frames + fps + durée.
- Slider double **en frames** (et non en secondes) : valeurs entières.
- Affichage des deux frames bornes en vignette grande taille.
- Boutons pas-à-pas `-1 frame` / `+1 frame` à gauche et à droite (précision pixel).
- Affichage de la durée résultante.
- Option "garder uniquement 1 frame sur N" (frame skipping) — utile pour réduire le poids en gardant la durée perçue.

**Pièges GIF.**

- Le `fps` reporté par MoviePy peut être un float (ex: 14.99) : caster en int pour cohérence.
- Certains GIFs ont des durées de frame variables (frame 1 = 100ms, frame 2 = 50ms) : prévenir et proposer une normalisation.

**Extensions.** Découpe multi-segments (sélectionner plusieurs intervalles à concaténer en un seul GIF), aperçu côte-à-côte avant/après en frames clés, export d'un PNG des frames sélectionnées séparément.

---

## 4. Resize & optimisation poids

**Description.** Optimise le poids d'un GIF en jouant sur les leviers spécifiques au format : dimensions, fps, taille de palette, frame skipping, dithering, compression lossy.

**Cas d'usage GIF.**

- GIF de 15 Mo à descendre sous les 5 Mo pour Discord.
- Optimisation drastique pour usage email signature (<1 Mo).
- Standardisation d'une bibliothèque de GIFs à une taille cible.

**Fonctions MoviePy + outils.** `vfx.Resize`, `clip.with_fps`, `clip.write_gif(..., opt="OptimizeTransparency", fuzz=10)`. Post-traitement via subprocess `gifsicle --optimize=3 --lossy=N --colors=M`.

**UI Streamlit.**

- Métadonnées avant/après en temps réel.
- Slider largeur (en conservant le ratio).
- Slider FPS cible (avec valeur source affichée).
- Slider taille de palette (32, 64, 128, 256 couleurs) + aperçu de la dégradation.
- Slider compression lossy gifsicle (0–200, 0 = aucune perte, 80 typique).
- Toggle dithering (Floyd-Steinberg, ordered, aucun).
- Option "frame skipping" (garder 1 frame sur 2, 1 sur 3…).
- **Estimateur de poids en direct** + affichage du % de réduction.
- Aperçu A/B (avant / après) avec switch instantané.

**Pièges GIF.**

- Réduction agressive de palette → bandes visibles (banding) sur gradients : recommander dithering.
- Frame skipping → mouvement saccadé : prévenir et désactiver pour GIFs déjà à bas fps.
- `gifsicle` doit être présent sur la machine : check au démarrage avec message d'erreur clair sinon.

**Extensions.** Compression "intelligente" qui teste plusieurs combinaisons de paramètres et propose le meilleur ratio qualité/poids (cf. page IA #34), histogramme de la palette, preview du palette de couleurs utilisée.

---

## 5. Concaténation de GIFs

**Description.** Assemble plusieurs GIFs bout à bout en un seul, avec gestion des résolutions et fps hétérogènes.

**Cas d'usage GIF.**

- Compiler plusieurs réactions en un GIF "best of".
- Créer un GIF tutoriel à partir d'étapes individuelles.
- Mashup créatif de plusieurs sources.

**Fonctions MoviePy.** `concatenate_videoclips([gif1, gif2, ...], method="chain"|"compose")`, précédé d'homogénéisation par `vfx.Resize` et `with_fps` si besoin.

**UI Streamlit.**

- Upload multiple de GIFs.
- Liste réordonnable (drag & drop via `streamlit-sortables`) avec vignette animée + nb frames + durée.
- Choix méthode : `chain` (rapide, exige dimensions identiques) ou `compose` (robuste, padding/centrage).
- Choix fps de sortie (max source, min source, ou personnalisé).
- Choix dimensions de sortie (max source, min source, personnalisé) — avec mode de remplissage (crop, letterbox, fond couleur).
- Option "ajouter une transition" (renvoi page 20).
- Tous les contrôles d'optimisation (cf. page 4) appliqués au résultat.

**Pièges GIF.**

- FPS différents → vitesse perçue différente d'un GIF à l'autre. Soit on normalise (recommandé), soit on prévient.
- Concatener 10 GIFs de 5 Mo = potentiellement 50 Mo : afficher poids estimé.

**Extensions.** Insertion automatique d'un cartonnage noir (1 frame) entre GIFs pour respiration, génération d'une grille planche-contact (3×3) en alternative à la concaténation linéaire.

---

## 6. Éditeur frame-by-frame ⭐

**Description.** **Fonctionnalité phare spécifique au GIF.** Vue de toutes les frames du GIF en mosaïque cliquable, avec actions par frame : supprimer, dupliquer (allonger la pause), réordonner, remplacer par une image externe, exporter en PNG. Aucun éditeur web n'offre cela proprement aujourd'hui.

**Cas d'usage GIF.**

- Supprimer 2 frames floues au milieu d'un GIF.
- Dupliquer la frame finale 5 fois pour créer une pause avant la boucle.
- Remplacer une frame par une version retouchée externement.
- Exporter chaque frame en PNG pour usage sticker pack.

**Fonctions MoviePy + numpy.** Itération sur les frames via `clip.iter_frames(fps=clip.fps)`, manipulation comme liste de `np.ndarray`, reconstruction via `ImageSequenceClip(frames, fps=fps)` puis `write_gif`.

**UI Streamlit.**

- Mosaïque cliquable de toutes les frames (vignettes), numérotées.
- Sélection multiple (Ctrl+click, plage Shift+click).
- Barre d'actions : Supprimer, Dupliquer (×N), Inverser ordre de la sélection, Remplacer par image…, Exporter en PNG.
- Édition de la durée de chaque frame individuellement (pour GIFs à durée variable de frame).
- Aperçu animé du résultat à tout moment.
- Historique d'actions (undo/redo).

**Pièges GIF.**

- Sur GIFs très longs (>200 frames), la mosaïque devient illisible : paginer ou virtualiser.
- Conserver les métadonnées de durée par frame si la source les a.
- Remplacement par image : vérifier dimensions cohérentes.

**Extensions.** Édition de la durée de chaque frame séparément (créer des pauses ciblées), mode "onion skin" (voir les frames adjacentes en surimpression pour cohérence), action "supprimer les frames en double" (détection par hash perceptuel).

---

# 🔵 Tier 2 — Essentiel pour l'édition GIF

## 7. Meme creator (texte sur GIF) ⭐

**Description.** **Cas d'usage massif des GIFs**. Génération de memes en ajoutant du texte stylisé (top text / bottom text classique, légende, dialogue) sur un GIF avec contrôle complet de typographie et timing.

**Cas d'usage GIF.**

- Meme classique "Top text / Bottom text" en Impact blanc avec contour noir.
- Légende explicative sur un GIF tutoriel.
- Dialogue bulles BD sur GIF de personnage.
- Réaction custom avec texte personnalisé.

**Fonctions MoviePy.** `TextClip(text, font, font_size, color, stroke_color, stroke_width, method="caption", size=(w, h))`, positionnement, `CompositeVideoClip([gif, text])`, `text.with_duration(gif.duration)` ou apparition temporisée.

**UI Streamlit.**

- Templates meme prédéfinis (Impact classique, sous-titre TV, citation, dialogue BD).
- Zone de saisie texte (multi-ligne).
- Choix de police (Impact, Helvetica Bold, Comic Sans, Bebas Neue, Roboto…).
- Slider taille, color picker texte + contour + fond box.
- Position : grille 9 zones + offset fin.
- Top text / Bottom text : deux champs séparés en preset meme.
- Timing : permanent / apparaît à frame N / animation typewriter.
- Bouton "Random meme" pour tester rapidement avec textes amusants.

**Pièges GIF.**

- Police Impact : licence Microsoft, embarquer une alternative libre (par ex. "Anton" qui s'en approche).
- Texte sur GIF coloré : prévoir contour noir épais par défaut (lisibilité).
- Caractères unicode : tester emoji et accents dès le début.

**Extensions.** Bibliothèque de templates meme populaires (Drake, Distracted Boyfriend, Two Buttons…), génération de captions IA (cf. page #29), animation par mot (TikTok-style), sticker text (texte sans fond).

---

## 8. Watermark / logo sur GIF

**Description.** Superpose un logo, un copyright ou une signature discrète sur le GIF.

**Cas d'usage GIF.**

- Marquer une bibliothèque de GIFs d'entreprise.
- Apposer un copyright sur des GIFs artistiques.
- Signature de créateur sur des stickers Telegram custom.

**Fonctions MoviePy.** `ImageClip("logo.png").with_duration(gif.duration)`, `with_position(...)`, `with_opacity(...)`, `resized(width=...)`, `CompositeVideoClip([gif, logo])`.

**UI Streamlit.**

- Upload PNG (avec alpha) ou JPG.
- Position : 9 zones + offset.
- Slider taille (% largeur GIF).
- Slider opacité.
- Aperçu intégré dans le GIF animé.

**Pièges GIF.**

- Petits GIFs (240px) avec logo trop gros : prévoir taille relative et limite minimale.
- Alpha continu du PNG vs alpha binaire du GIF : risque de halo, appliquer un seuil.

**Extensions.** Watermark tuilé sur toute l'image, watermark animé (clignotement, déplacement lent), date dynamique en texte.

---

## 9. Modification de vitesse

**Description.** Accélère ou ralentit un GIF, soit uniformément, soit avec ramping (lent → rapide → lent).

**Cas d'usage GIF.**

- Ralentir un GIF trop rapide pour mieux observer un détail.
- Accélérer pour boucle plus "snappy" sur réseaux sociaux.
- Ramping lent → rapide pour effet dramatique.

**Fonctions MoviePy.** `vfx.MultiplySpeed(factor)`, `vfx.AccelDecel(new_duration, abruptness, soonness)`, `clip.time_transform(...)` pour vitesse variable custom.

**UI Streamlit.**

- Slider facteur vitesse (0.1 à 5).
- Affichage durée résultante.
- Mode "ramping" avec sliders `abruptness` et `soonness` (avec courbe visuelle SVG).
- Note explicative : "Ralentir nécessite des frames sources nombreuses, sinon saccades — voir page IA #28 pour interpolation".

**Pièges GIF.**

- Slow-mo sous le fps source → saccades visibles (le GIF n'a pas plus de frames). Renvoyer vers la page d'interpolation IA.
- Très haute vitesse → GIF illisible (frame d'1ms).

**Extensions.** Vitesse par segments (rapide au début, lent à la fin), couplage avec interpolation IA pour slow-mo fluide.

---

## 10. Reverse / Boomerang ⭐

**Description.** **Effet emblématique des GIFs**. Joue le GIF à l'envers, ou en aller-retour boomerang pour boucle parfaite.

**Cas d'usage GIF.**

- Effet magique "reverse" (objet qui se reconstitue).
- Boomerang d'un mouvement (saut, sourire, geste).
- Création d'une boucle naturellement seamless (aller-retour ne montre jamais de coupure).

**Fonctions MoviePy.** `vfx.TimeMirror()` (reverse), `vfx.TimeSymmetrize()` (forward + reverse), `vfx.Loop(n=N)`.

**UI Streamlit.**

- Toggle 3 modes : Reverse seul, Boomerang (avant + arrière), Boomerang inversé (arrière + avant).
- Slider nombre de boucles (1 à 10 avant export).
- Aperçu boucle infinie dans l'UI.

**Pièges GIF.**

- Le boomerang double la durée et donc le poids : prévenir.
- Si on enchaîne reverse + une autre transformation, attention à l'ordre.

**Extensions.** Génération de plusieurs versions (forward / reverse / boomerang) en un export, combinaison avec vitesse pour effet stop-motion.

---

## 11. Crop, Rotation, Flip

**Description.** Manipulations géométriques de base : recadrage, rotation, miroir.

**Cas d'usage GIF.**

- Retirer un élément gênant en bord d'image.
- Tourner un GIF mal orienté.
- Mirror pour inverser une démo gauchère/droitière.

**Fonctions MoviePy.** `vfx.Crop(x1, y1, x2, y2)`, `vfx.Rotate(angle, expand=True, bg_color=...)`, `vfx.MirrorX()`, `vfx.MirrorY()`.

**UI Streamlit.**

- Aperçu de la première frame pour réglage.
- Crop interactif via `streamlit-cropper`.
- Champs numériques x, y, w, h pour précision.
- Boutons rapides rotation : -90°, +90°, 180°.
- Slider angle libre + couleur de fond (pour zones vides).
- Toggle mirror horizontal / vertical.
- Preset crop par ratio : 1:1, 4:5, 9:16, 16:9.

**Pièges GIF.**

- Rotation non-multiple de 90° → zones de fond, qui en GIF binaire-alpha sont opaques d'une couleur unie.
- Crop avec dimensions impaires : appliquer `vfx.EvenSize()` pour cohérence si conversion ultérieure en MP4.

**Extensions.** Crop par détection de sujet automatique (renvoi page IA #26), redresseur d'horizon, crop animé (zoom progressif sur une zone).

---

## 12. Contrôle de boucle & seamless loop ⭐

**Description.** **Spécifique au GIF.** Gère le nombre de boucles, et surtout produit des boucles **seamless** (sans coupure visible entre la fin et le début).

**Cas d'usage GIF.**

- Boucle infinie classique pour Discord/Slack.
- Boucle limitée (jouer 3 fois puis s'arrêter) pour effet narratif.
- Boucle parfaite pour fond animé site web / écran d'attente.

**Fonctions MoviePy + format.** `vfx.MakeLoopable(overlap_duration)` qui fait fondre la fin sur le début, `vfx.TimeSymmetrize` (palindrome = toujours seamless), `vfx.Loop`. Le nombre de boucles est un attribut du format GIF (`loop=0` infini, `loop=N` boucle N+1 fois), à passer à `write_gif`.

**UI Streamlit.**

- Slider "loop count" : infini (par défaut), 1, 2, 3, 5, 10.
- Mode seamless : aucun, fondu enchaîné (`MakeLoopable` avec slider overlap 0.5–3s), boomerang (`TimeSymmetrize`).
- Aperçu de la jonction fin → début spécifiquement (lecture en boucle de cette zone).
- Détection automatique du meilleur point de boucle (renvoi page IA #30).

**Pièges GIF.**

- `MakeLoopable` réduit la durée perçue de l'overlap.
- Sur GIFs très courts (<1s), seamless difficile : suggérer boomerang à la place.

**Extensions.** Détection automatique de la frame finale qui ressemble le plus à la frame initiale (similarité perceptuelle) puis trim à cette frame pour seamless naturel.

---

## 13. Reformatage de dimensions (carré, vertical, custom)

**Description.** Convertit un GIF dans le ratio cible d'une plateforme (carré pour Instagram, vertical pour stories, etc.).

**Cas d'usage GIF.**

- Adapter un GIF horizontal en carré pour profil/sticker.
- Format vertical pour intégration story / mobile.
- Standardisation d'une bibliothèque GIF à un ratio unique.

**Fonctions MoviePy.** `vfx.Resize`, `vfx.Crop`, `vfx.Margin` (pour bandes), `CompositeVideoClip` pour fonds custom.

**UI Streamlit.**

- Presets ratios : 1:1 carré, 9:16 vertical, 16:9 horizontal, 4:5 portrait Insta.
- Custom : dimensions libres.
- Mode remplissage : crop, letterbox (bandes noires/couleur), fond flou (duplication + flou Gaussien), image de fond.
- Position du sujet dans le frame final.
- Aperçu côte-à-côte.

**Pièges GIF.**

- Crop perd de l'information : prévenir si visages détectés en zone coupée.
- Fond flou = traitement double = poids potentiel doublé en frames.

**Extensions.** Reframe automatique IA (page #25), export multi-formats simultané, templates par plateforme (Telegram sticker 512×512, Instagram, etc.).

---

# 🟣 Tier 3 — Pages créatives spécifiques GIF

## 14. Filtres colorimétriques et palettes artistiques

**Description.** Galerie de filtres style "Instagram" appliqués au GIF, plus des palettes artistiques spécifiques GIF (8-bit, monochrome, duotone, retro).

**Cas d'usage GIF.**

- Donner un look cohérent à une série de GIFs (branding).
- Effet rétro / vintage pour memes ironiques.
- Conversion noir et blanc dramatique.
- Look "GameBoy" 4 couleurs.

**Fonctions MoviePy.** `vfx.BlackAndWhite`, `vfx.InvertColors`, `vfx.LumContrast`, `vfx.GammaCorrection`, `vfx.MultiplyColor`, `vfx.Painting`. Filtres custom via `image_transform` (sépia, duotone, palette restreinte avec PIL `quantize`).

**UI Streamlit.**

- Galerie de presets (vignettes générées à la volée) : N&B, Sépia, Vintage, Cold blue, Warm sunset, GameBoy (4 verts), CGA (4 couleurs), 8-bit pixel art, Risograph, Cyberpunk, Film noir.
- Mode personnalisé : sliders luminosité, contraste, saturation, gamma, balance R/G/B.
- **Palette personnalisée** (spécifique GIF) : sélection manuelle de N couleurs vers lesquelles quantifier tout le GIF (effet stylisé puissant).
- Aperçu temps réel sur frame fixe.

**Pièges GIF.**

- Quantification trop agressive → banding visible.
- Palette personnalisée + dithering : tester les combinaisons.

**Extensions.** Import de LUTs `.cube`, génération de palette depuis une image de référence (extraction des N couleurs dominantes via k-means), couplage avec style transfer IA (page #27).

---

## 15. Création de GIF depuis séquence d'images

**Description.** Génère un GIF à partir d'une série d'images statiques (PNG/JPG), avec durée par image, transitions, et boucle.

**Cas d'usage GIF.**

- Avant/après en GIF (deux images alternées).
- Slideshow rapide de photos.
- Animation stop-motion à partir de prises individuelles.
- Démo step-by-step (3–5 screenshots animés).

**Fonctions MoviePy.** `ImageClip(path).with_duration(d)`, `concatenate_videoclips([...], method="compose")`, `ImageSequenceClip(folder_or_list, fps=...)`, `write_gif`.

**UI Streamlit.**

- Upload multiple (drag & drop ordonné).
- Mosaïque réordonnable des images.
- Durée par image (uniforme ou individuelle).
- FPS de sortie.
- Transitions entre images (aucune, crossfade, slide).
- Effet Ken Burns optionnel (zoom + pan sur chaque image).
- Boucle (cf. page 12).

**Pièges GIF.**

- Images de tailles hétérogènes : choisir crop / letterbox / resize.
- Stop-motion : bien gérer la durée par frame (souvent on veut 100ms = 10fps).

**Extensions.** Mode "before/after" optimisé (2 images, transition slide ou wipe entre les deux), templates pour patterns courants (loading spinner, comparison, demo).

---

## 16. Picture-in-picture sur GIF

**Description.** Superpose un GIF secondaire (réaction, incrustation, watermark animé) sur un GIF principal.

**Cas d'usage GIF.**

- GIF de jeu vidéo + GIF de réaction du joueur en coin.
- Tutoriel GIF + flèche animée superposée.
- Carte interactive avec marqueur clignotant.

**Fonctions MoviePy.** `CompositeVideoClip([main_gif, secondary.with_position(...).resized(...).with_start(...)])`.

**UI Streamlit.**

- Upload GIF principal + GIF secondaire (overlay).
- Position de l'overlay (grille 9 zones + offset fin).
- Slider taille de l'overlay (10–40 % largeur).
- Forme : rectangle, rectangle arrondi, cercle (mask custom).
- Bordure / ombre portée.
- Timing apparition / disparition.

**Pièges GIF.**

- Durées différentes : choisir boucler / freeze / disparaître.
- Performance : composition de 2 GIFs = 2× le temps de rendu.
- Synchroniser les fps des deux GIFs pour fluidité.

**Extensions.** Suivi automatique d'un sujet pour positionner l'overlay (page IA #26 adapté), plusieurs overlays simultanés.

---

## 17. Mosaïque et split-screen de GIFs

**Description.** Affiche plusieurs GIFs simultanément en grille (côte-à-côte, 2×2…).

**Cas d'usage GIF.**

- Comparaison de plusieurs versions/itérations d'un design en GIF.
- Réaction multi-personnes synchronisée.
- Démo d'un même mouvement sous différents angles.

**Fonctions MoviePy.** `clips_array([[g1, g2], [g3, g4]])` (helper natif), ou `CompositeVideoClip` avec positionnement manuel.

**UI Streamlit.**

- Choix layout : 1×2, 2×1, 2×2, 1×3, 3×1, 3×3.
- Upload des N GIFs.
- Padding entre cellules + couleur de fond.
- Synchronisation start (tous à 0, ou décalages individuels).
- Étiquettes textuelles par cellule (optionnel).
- Boucle commune (durée = max ou min des GIFs).

**Pièges GIF.**

- Durées différentes : padding noir, boucle de la plus courte, ou couper la plus longue.
- Poids cumulé : grille 2×2 de GIFs de 5 Mo = ~20 Mo potentiels.

**Extensions.** Layouts asymétriques (un grand + plusieurs petits), animation séquentielle des cellules.

---

## 18. Mode Sticker (GIF transparent) ⭐

**Description.** **Cas d'usage spécifique GIF.** Génère un GIF avec fond transparent, utilisable comme sticker (Telegram, Discord) ou élément graphique animé incrustable. Nécessite le détourage du sujet (intersection avec la page #23 IA pour le matting automatique).

**Cas d'usage GIF.**

- Stickers Telegram animés (format 512×512, fond transparent obligatoire).
- Éléments graphiques pour intégrations web (mascotte animée).
- Composants pour montage ultérieur sans halo de fond.

**Fonctions MoviePy + GIF.** `clip.with_mask(mask_clip)`, export `write_gif(out, opt="OptimizeTransparency", transparent=True)`. Le mask doit être binaire pour le GIF (seuillage du masque alpha continu).

**UI Streamlit.**

- Upload du GIF source.
- Choix méthode de détourage :
  - Chroma key (`vfx.MaskColor` avec couleur cible + tolérance) si fond uni.
  - Matting IA automatique (renvoi page #23).
  - Masque manuel dessiné (`streamlit-drawable-canvas`).
- Slider seuil alpha (binarisation du masque continu).
- Slider "feather" / lissage des bords (érosion-dilatation morphologique).
- Aperçu sur fond damier (style Photoshop) pour vérifier le détourage.
- Couleur de fond de remplacement pour export GIF (puisque GIF ne supporte pas l'alpha vrai, on peut soit garder le sticker avec un fond magenta keyed, soit exporter en APNG/WebP qui supportent l'alpha continu).

**Pièges GIF.**

- Alpha binaire du GIF → halo de couleur du fond original sur les bords. Solution : érosion légère du masque (1–2 px).
- Pour stickers Telegram : contraintes strictes (taille 512×512, <256 Ko, <30 fps).
- Si on veut un sticker propre avec semi-transparence, préférer **WebP animé** ou **APNG** plutôt que GIF.

**Extensions.** Export multi-format simultané (GIF avec fond magenta keyed + WebP avec alpha vrai), preview directe sur fonds variés (clair, sombre, coloré), kit de stickers (batch sur dossier).

---

## 19. Remplacement de fond ⭐

**Description.** **La question posée.** Remplace le fond d'un GIF par une image fixe, une couleur unie, ou un autre GIF animé. Couplé au matting IA (page #23) pour les cas non-chroma key.

**Cas d'usage GIF.**

- Personnage filmé sur fond simple → fond fantaisie (espace, scène).
- Mascotte d'entreprise sur fond corporate.
- Combinaison de deux GIFs (sujet d'un + fond d'un autre).

**Fonctions MoviePy.** Pipeline complet :

1. `gif = VideoFileClip("input.gif")`.
2. Génération du masque (chroma key via `vfx.MaskColor`, ou matting IA, ou masque manuel).
3. `gif_with_mask = gif.with_mask(mask_clip)`.
4. `new_bg = ColorClip(...) | ImageClip(...).with_duration(gif.duration) | VideoFileClip("bg.gif").loop(duration=gif.duration)`.
5. `final = CompositeVideoClip([new_bg, gif_with_mask], size=gif.size)`.
6. `final.write_gif(...)`.

**UI Streamlit.**

- Upload GIF source.
- Choix méthode de génération du masque :
  - **Chroma key** : color picker pour la couleur du fond actuel + slider tolérance + slider feather. Idéal si fond uni (vert, bleu, blanc).
  - **Matting IA** : choix modèle (RVM pour cohérence temporelle, MediaPipe pour personnes, BiRefNet pour qualité) — voir page #23.
  - **Masque manuel** : éditeur via `streamlit-drawable-canvas` sur quelques frames clés + interpolation.
- Choix du nouveau fond :
  - Couleur unie (`st.color_picker`).
  - Image fixe (upload PNG/JPG).
  - GIF animé (upload, bouclé sur la durée).
  - Dégradé (deux couleurs + angle).
  - Flou du fond original (effet portrait, conserve l'ambiance).
- Aperçu avec switch instantané "masque seul / sujet sur damier / sujet sur nouveau fond".
- Sliders fins : seuil alpha, érosion bords, dilatation, blur des bords.

**Pièges GIF.**

- Alpha binaire → bord net = halo de couleur du fond original. Critique d'avoir un slider d'érosion.
- Si fond cible animé : aligner les durées (boucler le fond ou couper).
- Matting IA frame-par-frame (BiRefNet) → flicker. Préférer RVM (vidéo-native).
- Cheveux / éléments fins : matting toujours imparfait, prévenir.

**Extensions.** Bibliothèque de fonds prédéfinis (espace, plage, studio, gradient, abstract patterns), génération de fond par IA (texte → image via Stable Diffusion), animation de fond (parallax, scroll lent).

---

## 20. Transitions entre GIFs

**Description.** Insère des transitions douces entre plusieurs GIFs concaténés (cross-fade, slide, zoom, glitch).

**Cas d'usage GIF.**

- Adoucir les raccords d'un GIF compilation.
- Effet stylé entre étapes d'un tutoriel.
- Transition créative pour mashup.

**Fonctions MoviePy.** `vfx.CrossFadeIn`, `vfx.CrossFadeOut`, `vfx.SlideIn`, `vfx.SlideOut`, composition avec offsets temporels.

**UI Streamlit.**

- Liste des GIFs (cf. page 5).
- Type de transition (global ou par paire) : crossfade, slide, fade-to-color, zoom, wipe, glitch (custom effect).
- Durée transition (0.2–1.5s).
- Aperçu de chaque raccord.

**Pièges GIF.**

- Transitions de courte durée nécessaires (les GIFs sont courts) : éviter > 1s.
- Crossfade entre GIFs très différents visuellement = effet "soupe" : prévenir.

**Extensions.** Transitions custom dessinées (wipe avec mask animé), bibliothèque de transitions "fun" (glitch, RGB split, pixelize).

---

## 21. Masques de forme (cercle, custom)

**Description.** Découpe le GIF dans une forme arbitraire (cercle, étoile, masque personnalisé), produisant un GIF "découpé" pour intégration créative.

**Cas d'usage GIF.**

- Avatar circulaire animé.
- Sticker en forme spécifique.
- Élément décoratif pour site web (forme custom).

**Fonctions MoviePy.** Création d'un `ImageClip` masque (numpy array), application via `clip.with_mask(mask)`, composition.

**UI Streamlit.**

- Choix de forme : cercle, ellipse, étoile, hexagone, cœur, custom (upload PNG masque noir/blanc).
- Position du centre.
- Taille / rayon.
- Slider feather (lissage des bords).
- Couleur de fond (ou transparent pour mode sticker).

**Pièges GIF.**

- Alpha binaire → bords pixellisés sur formes complexes. Suggérer APNG/WebP pour qualité parfaite.
- Performance : masque calculé sur chaque frame, mais ImageClip mask est cached.

**Extensions.** Animation du masque (cercle qui grandit/rétrécit), masques multiples (kaléidoscope).

---

## 22. Effets glitch / VHS / rétro

**Description.** Effets stylisés très populaires dans la culture GIF : RGB split, VHS noise, datamosh, scanlines, pixelisation.

**Cas d'usage GIF.**

- Effet "aesthetic" / vaporwave pour réseaux sociaux.
- Glitch artistique pour cover album / promotion.
- Stylisation rétro 80s-90s.

**Fonctions MoviePy + custom.** Implémentés via `image_transform` avec numpy/OpenCV :

- RGB split : décalage des canaux R, G, B.
- Scanlines : multiplication par un masque alterné.
- VHS noise : ajout de bruit Gaussien + tracking errors.
- Datamosh : duplication de blocs entre frames.
- Pixelisation : downscale + upscale nearest.
- Chromatic aberration : warp par canal.

**UI Streamlit.**

- Galerie d'effets en vignettes preview.
- Sliders d'intensité par effet.
- Possibilité de combiner plusieurs effets (pile ordonnée).
- Aperçu temps réel sur frame fixe puis sur animation.

**Pièges GIF.**

- Bruit aléatoire frame-par-frame augmente la complexité de la palette → poids GIF gonfle. Suggérer post-compression.
- Datamosh nécessite manipulation des frames brutes (intercaler).

**Extensions.** Combo presets (full VHS look, full glitch art, vaporwave), randomisation contrôlée pour variations.

---

# 🤖 Tier IA — GIF augmenté par modèles d'intelligence artificielle

> Pages où l'IA débloque des capacités impossibles à atteindre en pur traitement d'image. Toutes les recommandations privilégient des modèles **légers, ONNX/CPU-compatibles** quand possible, pour rester fidèles à la promesse de traitement local.

---

## 23. Détourage automatique du sujet (matting IA) ⭐⭐

**Description.** Génère automatiquement un masque alpha cohérent pour isoler le sujet (personne, animal, objet) du fond, sans intervention manuelle. **C'est la brique IA centrale** sur laquelle s'appuient pages #18 (sticker), #19 (background replacement), #21 (shape mask combiné), #34 (extraction sujet).

**Cas d'usage GIF.**

- Détourer un personnage pour sticker.
- Préparer un GIF pour changement de fond.
- Extraire un élément pour réutilisation dans un autre montage.

**Stack technique recommandée.**

- **RVM (Robust Video Matting)** — modèle de référence pour GIF. Conçu spécifiquement pour la vidéo, garantit la cohérence temporelle (pas de flicker entre frames). Versions ONNX/CPU disponibles, ~5 Mo. Idéal pour personnes et animaux.
- **MediaPipe SelfieSegmentation** — ultra léger (tourne en temps réel CPU), personnes seulement, moins précis sur les bords mais suffisant pour beaucoup de cas.
- **BiRefNet** — qualité supérieure (objets génériques, pas que personnes), mais image-par-image donc flicker possible. À réserver aux cas statiques ou avec post-traitement de cohérence temporelle.
- **SAM 2 (Segment Anything Model v2)** — sublime mais lourd (GPU recommandé). À proposer en option "qualité maximale".

**UI Streamlit.**

- Upload GIF.
- Choix modèle (vitesse vs qualité) avec temps estimé.
- Slider seuil de binarisation (pour export GIF).
- Slider lissage bords (érosion / dilatation / blur).
- Aperçu sur fond damier + sur fond coloré + sur fond image.
- Toggle "améliorer cohérence temporelle" (post-filtre Gaussien temporel sur les masques pour réduire le flicker des modèles image-only).

**Pièges GIF.**

- Le masque continu (alpha 0–255) ne peut pas être stocké dans le GIF final : il faut binariser. Toujours afficher l'aperçu du résultat final binarisé, pas seulement le masque continu.
- Cheveux fins / éléments transparents (verres, voile) : qualité variable.
- Si export en WebP/APNG, on conserve l'alpha continu — proposer ces formats en alternative.

**Extensions.** Export du masque seul en GIF noir/blanc (utile pour autres logiciels), batch sur dossier de GIFs, masque animé (le sujet s'efface progressivement).

---

## 24. Détection de visages + floutage automatique

**Description.** Détecte tous les visages dans le GIF et applique un floutage / pixelisation pour anonymisation, sans intervention manuelle.

**Cas d'usage GIF.**

- Anonymiser un GIF capturé en public pour partage.
- Protéger des mineurs sur un GIF de famille devenu meme.
- Conformité RGPD pour usage entreprise.

**Stack technique.** `MediaPipe FaceDetection` (ultra léger, CPU), `RetinaFace` (qualité supérieure), ou `YOLOv8-face`. Tracking inter-frames via DeepSORT ou simple IoU pour cohérence.

**UI Streamlit.**

- Upload GIF.
- Toggle modèle (vitesse vs précision).
- Type de masquage : flou Gaussien, mosaïque (pixelisation), ovale noir, emoji 😀.
- Slider seuil confiance détection.
- Mode "exclure certains visages" : scan préalable qui liste les visages uniques détectés (clustering embeddings), l'utilisateur coche ceux à NE PAS flouter.
- Padding autour du visage (le flou doit dépasser légèrement).

**Pièges GIF.**

- Détection ratée sur 1 frame → trou visible dans la boucle. Filtrage temporel obligatoire (combler les trous par interpolation des bounding boxes).
- Visages très petits (GIF 240px) : limite de détection.

**Extensions.** Détection de plaques d'immatriculation (modèle ALPR), de texte (`EasyOCR` + flou), de tatouages.

---

## 25. Reframe intelligent (subject-tracking crop)

**Description.** Convertit un GIF d'un ratio à un autre (16:9 → 1:1, horizontal → vertical) en gardant **automatiquement** le sujet principal centré dans le crop dynamique.

**Cas d'usage GIF.**

- GIF horizontal extrait de YouTube → format carré pour Instagram.
- GIF de gameplay 16:9 → format 9:16 sticker mobile.

**Stack technique.** Détection de saillance ou personne (MediaPipe / YOLO) sur chaque frame → trajectoire de centre d'intérêt → lissage temporel (filtre passe-bas) → crop dynamique via `clip.transform(crop_function)`.

**UI Streamlit.**

- Choix ratio cible.
- Choix algo : visages, personnes, saillance générique, hybride.
- Slider "stabilité" du tracking (lissage).
- Aperçu de la trajectoire de crop (rectangle qui se déplace sur l'aperçu).
- Toggle "comportement multi-sujets" : suivre le plus grand / faire un compromis / split-screen.

**Pièges GIF.**

- Tremblement de crop sur GIF court : appliquer un lissage agressif (le GIF est trop court pour des mouvements complexes de toute façon).
- Sujet sortant du cadre source : on ne peut pas inventer de pixels.

**Extensions.** Match-cut intelligent qui change de sujet entre frames, mode "zoom in" progressif vers le sujet.

---

## 26. Style transfer / GIF stylisé par IA ⭐

**Description.** Applique un style visuel (peinture, anime, sketch, pixel art) à tout le GIF via modèles génératifs ou neural style transfer.

**Cas d'usage GIF.**

- Convertir un GIF réaliste en style Studio Ghibli / Pixar / comic.
- Style "oil painting" pour effet artistique.
- Conversion en pixel art animé.
- Sketch / line art noir et blanc.

**Stack technique.**

- **AnimateDiff + ControlNet** : conditionnement temporel propre, mais coûteux.
- **Stable Diffusion img2img frame-par-frame** : simple mais flicker garanti sans astuces (TokenFlow, Rerender A Video).
- **Modèles légers** : `AnimeGANv3` (style anime, ONNX/CPU possible), `style-transfer-pytorch` pour transfert depuis image de référence.
- **Real-ESRGAN-anime** pour passes finales.

**UI Streamlit.**

- Upload GIF + (optionnel) image de référence du style.
- Galerie de styles prédéfinis (anime, Pixar, oil painting, watercolor, pencil sketch, comic book, pixel art 8-bit, vaporwave).
- Slider "force" du style (0–100 %).
- Toggle "cohérence temporelle" (active TokenFlow / temporal smoothing, plus lent).
- Choix moteur : local ONNX (limité, rapide) ou API cloud (qualité supérieure, payant).

**Pièges GIF.**

- Flicker frame-par-frame sans modèle vidéo-natif : avertir.
- Coût : style transfer sur 60 frames = 60 inférences SD ≈ plusieurs minutes même en GPU.
- Préférer modèles légers ONNX pour rester local (AnimeGAN).

**Extensions.** Style partiel (seulement sur le sujet via masque page #23), style depuis vidéo de référence (apprendre un style spécifique), animation depuis image fixe stylisée.

---

## 27. Upscaling / amélioration qualité ⭐

**Description.** Augmente la résolution et la netteté d'un GIF basse qualité (240p, JPEG-artifacts visibles) via modèles de super-résolution.

**Cas d'usage GIF.**

- Récupérer un GIF historique de mauvaise qualité.
- Upscale d'un meme classique pour usage moderne (4K).
- Amélioration d'un screencast capturé en basse résolution.

**Stack technique.** `Real-ESRGAN` (modèle de référence, version `RealESRGAN_x4plus` ou `realesr-animevideov3` pour contenu animé), `GFPGAN` pour visages spécifiquement, `Anime4K` pour contenu anime/dessins. Versions ONNX disponibles.

**UI Streamlit.**

- Upload GIF.
- Choix facteur upscale (×2, ×3, ×4).
- Choix modèle : générique (`Real-ESRGAN x4`), anime (`realesr-animevideov3`), visages (`GFPGAN`).
- Slider "force" de l'amélioration.
- Aperçu côte-à-côte before/after sur une frame zoomée.

**Pièges GIF.**

- Le résultat upscalé peut devenir très lourd : prévenir.
- Real-ESRGAN ajoute des "détails" parfois inventés : pas idéal pour contenu où la fidélité compte.
- CPU lent (~1 frame/s) : barre de progression critique.

**Extensions.** Couplage avec frame interpolation (page #28) pour produire un GIF 4K à 60fps depuis une source 480p 15fps, restauration spécifique des artefacts JPEG.

---

## 28. Frame interpolation (slow-mo fluide) ⭐

**Description.** Génère des frames intermédiaires synthétiques entre les frames existantes du GIF, permettant un slow-motion fluide ou un upscale temporel (15 → 60 fps).

**Cas d'usage GIF.**

- Ralentir un GIF sans saccades (slow-mo cinéma).
- Augmenter le fps d'un GIF saccadé.
- Préparer un GIF basse-fps pour conversion en MP4 60fps qualité.

**Stack technique.** `RIFE (Real-Time Intermediate Flow Estimation)`, `FILM (Frame Interpolation for Large Motion)`, ou `DAIN`. RIFE est le meilleur compromis vitesse/qualité, version ONNX disponible. Pipeline : extraire frames → générer N frames intermédiaires par paire → reconstruire GIF avec nouveau fps.

**UI Streamlit.**

- Upload GIF + métadonnées actuelles (fps, nb frames).
- Choix : multiplier le fps (×2, ×4, ×8), ou ralentir (×0.5, ×0.25 sans perte de fluidité).
- Choix modèle : RIFE (rapide), FILM (haute qualité).
- Aperçu d'une portion ralentie.

**Pièges GIF.**

- Mouvements très rapides ou flous → artefacts d'interpolation (warping).
- Multiplier par ×8 → poids du GIF multiplié d'autant.
- Combinaison logique avec page #9 (vitesse) : si on ralentit ×4, interpoler ×4 maintient la fluidité.

**Extensions.** Frame interpolation sélective (seulement sur certaines portions où le mouvement est intéressant), combinaison avec upscaling pour un "remaster" complet.

---

## 29. Génération de caption / meme text par LLM ⭐

**Description.** Analyse visuelle du GIF (CLIP / GPT-4V / Claude Vision) puis génération automatique de propositions de captions / textes de meme adaptés au contenu.

**Cas d'usage GIF.**

- Trouver le bon texte pour transformer un GIF en meme.
- Générer plusieurs variations de captions à tester.
- Idéation rapide pour créateurs de contenu.

**Stack technique.** Envoi de N frames clés (extraites par exemple aux quartiles temporels) à un modèle multimodal (Claude 3.5 Sonnet, GPT-4o, Gemini Vision). Prompt structuré : "Voici 4 frames d'un GIF. Propose 5 captions courtes humoristiques style meme."

**UI Streamlit.**

- Upload GIF.
- Choix modèle LLM (avec note coût API).
- Style de caption : meme classique, légende ironique, citation philosophique, réaction, marketing.
- Génération de N propositions (3–10).
- Bouton "régénérer" et "raffiner ce texte".
- Sélection d'une caption → renvoi direct vers la page meme creator (#7) pré-rempli.

**Pièges GIF.**

- Coût API : ~$0.01 par génération avec Claude Sonnet.
- Qualité humoristique très variable selon culture / langue : laisser l'utilisateur ajuster.
- Hallucinations possibles (description incorrecte du GIF).

**Extensions.** Génération multi-langues simultanée, learning sur les memes existants pour styles précis (database de templates), génération de captions par persona ("dis-le comme un sarcastique" / "comme un boomer").

---

## 30. Détection automatique du meilleur point de boucle ⭐

**Description.** Analyse le GIF pour identifier le couple (frame_début, frame_fin) qui produit la **boucle la plus seamless possible**, puis trim automatiquement à ces bornes.

**Cas d'usage GIF.**

- Convertir un clip vidéo arbitraire en GIF parfaitement seamless.
- Optimiser un GIF existant qui a une coupure visible.
- Préparer des GIFs ambient pour fond de site web.

**Stack technique.** Calcul de la similarité perceptuelle entre toutes les paires de frames (`SSIM`, `LPIPS`, ou simple distance L2 sur features CLIP). Recherche du couple (i, j) avec j-i ≥ durée minimale qui minimise la distance perceptuelle.

**UI Streamlit.**

- Upload GIF (ou vidéo source).
- Slider durée minimale de la boucle.
- Calcul + affichage de la matrice de similarité (heatmap).
- Top 5 propositions de bornes (chacune avec aperçu de la boucle).
- Validation manuelle ou auto-apply.

**Pièges GIF.**

- Sur des GIFs où aucune paire ne se ressemble : prévenir et suggérer `MakeLoopable` à la place.
- Calcul O(N²) : sur GIFs très longs, sampler les frames.

**Extensions.** Combinaison avec `MakeLoopable` (point de boucle + petit fondu pour seamless garanti), aperçu en boucle infinie directement dans l'app.

---

## 31. Animer une image statique en GIF (image → GIF) ⭐

**Description.** Génère un GIF animé à partir d'une **image fixe** via modèles génératifs : portrait qui parle, paysage qui bouge, objet qui s'anime.

**Cas d'usage GIF.**

- Animer un portrait pour avatar dynamique.
- Donner vie à une photo de vacances (eau qui bouge, ciel qui défile).
- Créer un GIF artistique à partir d'une illustration.

**Stack technique.**

- **Stable Video Diffusion (SVD)** : image → vidéo courte (4–14 frames), bon pour scènes générales. Modèle lourd, GPU obligatoire ou API.
- **LivePortrait** : spécialisé portraits, anime un visage statique avec une vidéo source ou des expressions paramétrées. CPU possible, ~100 Mo.
- **AnimateDiff** avec image conditionnante.
- **SadTalker** : portrait + audio → portrait qui parle.

**UI Streamlit.**

- Upload image fixe.
- Choix moteur : SVD (scène générale), LivePortrait (portrait), SadTalker (portrait + audio TTS).
- Pour SVD : prompt de direction du mouvement ("zoom in", "panning right", "subtle motion").
- Pour LivePortrait : choix d'expression (sourire, clin d'œil, tête qui bouge) ou upload d'une vidéo source de mimétisme.
- Durée GIF cible.
- Génération + aperçu + régénération.

**Pièges GIF.**

- SVD coûteux (GPU ou API), génère 14 frames à 24 fps → ~600ms de GIF natif, à étendre par interpolation pour usage typique.
- LivePortrait reste local et léger, idéal pour cette app.
- Cohérence : génération aléatoire, plusieurs régénérations parfois nécessaires.

**Extensions.** Combinaison animation + style transfer (animer puis styliser), galerie de styles d'animation pré-configurés (gentle breeze, dramatic zoom, etc.).

---

## 32. Quantification intelligente de palette (IA optimization)

**Description.** Optimise la palette 256 couleurs du GIF de façon intelligente, en analysant le contenu pour choisir les couleurs les plus représentatives perceptuellement, et en testant plusieurs combinaisons de paramètres pour trouver le meilleur ratio qualité/poids.

**Cas d'usage GIF.**

- Compression optimale d'un GIF complexe (paysage, photo).
- Réduction maximale du poids sans perte perceptible.
- Standardisation d'une palette artistique cohérente sur une série.

**Stack technique.** K-means en espace perceptuel (LAB / OKLAB plutôt que RGB) sur un échantillon de pixels, ou modèles dédiés (`Pillow.quantize` avec `MEDIANCUT`, `MAXCOVERAGE`, `FASTOCTREE`). Optionnellement : `pyspng` + boucle d'optimisation sur dithering + lossy + colors qui minimise le poids sous une contrainte de SSIM.

**UI Streamlit.**

- Upload GIF.
- Mode "auto" : l'app teste 10–20 combinaisons (palette × dithering × lossy) et propose les 3 meilleures sur le plan poids/qualité (graphe Pareto).
- Mode manuel : sliders fins.
- Visualisation de la palette retenue (256 carrés de couleur).
- Indicateurs : poids final, SSIM par rapport à l'original, gain en % vs export naïf.

**Pièges GIF.**

- Coût compute : mode auto = 20 exports successifs → plusieurs minutes. Barre de progression critique.
- L'optimum dépend du contenu (un GIF graphique tolère moins de couleurs qu'une photo).

**Extensions.** Palette imposée (l'utilisateur fournit une palette artistique, le GIF est quantifié vers celle-ci), bibliothèque de palettes thématiques (Game Boy, NES, vintage).

---

## 33. Détection NSFW / modération automatique

**Description.** Analyse le GIF pour détecter du contenu inapproprié et avertir l'utilisateur, utile en contexte communautaire (modération de soumissions de GIFs).

**Cas d'usage GIF.**

- Modération d'une bibliothèque de GIFs partagée en équipe.
- Conformité plateforme avant upload.
- Filtre familial.

**Stack technique.** `opennsfw2`, `Falconsai/nsfw_image_detection`, ou classifier CLIP avec prompts custom. Application sur N frames échantillonnées.

**UI Streamlit.**

- Upload GIF.
- Catégories analysées (cases à cocher) : NSFW, violence, contenu choquant.
- Seuils de sensibilité.
- Rapport par frame (timeline avec markers de score).
- Action proposée si détection : flou auto / suppression / rejet.

**Pièges GIF.**

- Faux positifs fréquents (anatomie médicale, art figuratif).
- Toujours laisser le contrôle final à l'humain.

**Extensions.** Couplage avec page #24 (anonymisation + modération en un pipeline), batch sur dossier.

---

## 34. Extraction de sujet → kit de stickers ⭐

**Description.** À partir d'un GIF, génère automatiquement un kit de stickers : sujet détouré exporté en GIF transparent, plusieurs poses isolées en PNG, variations de format.

**Cas d'usage GIF.**

- Créer un sticker pack Telegram à partir d'une vidéo personnelle.
- Générer des assets animés pour intégration dans des présentations.
- Bibliothèque d'éléments réutilisables pour montages futurs.

**Stack technique.** Combinaison page #23 (matting RVM) + détection des moments-clés (`PySceneDetect` ou heuristique sur le mouvement) + export multi-format en boucle.

**UI Streamlit.**

- Upload GIF source.
- Génération automatique : 6–10 stickers (variations de durée, format, fond).
- Galerie des résultats avec download individuel.
- Format de sortie : GIF transparent, WebP animé (alpha continu), APNG, PNG des frames clés.
- Bouton "Telegram pack" : applique automatiquement les contraintes Telegram (512×512, <256 Ko, <30 fps, format WebP animé).

**Pièges GIF.**

- Qualité dépendante du matting (cf. page #23).
- Format Telegram strict, valider toutes les contraintes.

**Extensions.** Génération d'un fichier ZIP de pack complet prêt à upload, intégration Telegram API pour upload direct, mode "expressions" qui génère N stickers correspondant à N moments expressifs (sourire, surprise, clin d'œil) détectés via analyse d'expression.

---

# 📋 Synthèse et roadmap recommandée

## Tableau récapitulatif

| Tier       | Pages | Spécificité GIF | Effort      | Valeur          |
| ---------- | ----- | --------------- | ----------- | --------------- |
| 🟢 Tier 1  | 6     | Moyenne à forte | Faible      | Très élevée     |
| 🔵 Tier 2  | 7     | Forte           | Moyen       | Élevée          |
| 🟣 Tier 3  | 9     | Très forte      | Moyen-élevé | Différenciation |
| 🤖 Tier IA | 12    | Variable        | Élevé       | Wow effect      |

## Roadmap recommandée

**Sprint 1 — Fondations (1–2 semaines).** Architecture multipage, module commun (uploads, preview, cache, progress logger), pages 1 (Video→GIF) + 4 (Resize) + 5 (Concat). C'est le squelette livrable.

**Sprint 2 — MVP éditeur (2 semaines).** Pages 2 (GIF→Video), 3 (Trim frame-precise), **6 (Frame editor — la killer feature)**, 7 (Meme creator). À ce stade l'app est déjà compétitive avec Ezgif sur le cœur d'usage.

**Sprint 3 — Polish & boucle (1 semaine).** Pages 8 (Watermark), 9 (Vitesse), 10 (Reverse/Boomerang), 12 (Loop control). La page 12 est critique pour la qualité perçue.

**Sprint 4 — Différenciation (2 semaines).** Pages 11 (Crop/Rotate), 13 (Reformat), 14 (Filtres), 18 (Sticker mode), 19 (Background replacement — cas d'usage initial). Page 18 et 19 ouvrent la voie vers le tier IA.

**Sprint 5 — IA légère first (2 semaines).** **Page 23 (matting RVM)** en priorité absolue (débloque #18, #19), puis page 24 (face blur), puis page 29 (caption LLM via API). Ces 3 pages utilisent des modèles ONNX/CPU ou API, donc déployables sans GPU.

**Sprint 6+ — Pages créatives et IA lourdes.** Le reste selon retours utilisateurs. Privilégier pages 22 (glitch effects), 30 (auto-loop), 27 (upscaling) en early. Réserver 26 (style transfer) et 31 (image→GIF) pour quand l'infra GPU/API est en place.

## Différenciateurs uniques à mettre en avant marketing

Trois propositions de valeur que **aucun concurrent local** n'offre aujourd'hui :

1. **Éditeur frame-by-frame visuel** (page 6) — Ezgif n'a qu'un éditeur basique, Photoshop a la timeline mais pas une mosaïque cliquable claire.
2. **Détourage IA local et changement de fond** (pages 19 + 23) — toutes les solutions actuelles sont cloud (Runway, Kapwing) avec upload obligatoire.
3. **Optimisation intelligente palette + format** (pages 4 + 32) — gain de 30–60 % de poids par défaut sans intervention manuelle, alors qu'Ezgif laisse l'utilisateur tâtonner.

## Points d'attention transverses

- **Format de sortie multi-modal** : GIF par défaut mais toujours proposer WebP animé / APNG / MP4 en alternative. Le WebP animé est l'avenir, pousser sa découverte.
- **Profiling poids** : afficher en permanence le poids estimé / réel et le % de réduction vs source. C'est l'indicateur n°1 dans l'édition GIF.
- **Aperçu animé permanent** : `st.image(gif_bytes)` rejoue le GIF en boucle dans le navigateur, beaucoup plus utile qu'une frame statique.
- **Cache agressif** : hash du fichier + paramètres → mise en cache des résultats intermédiaires (matting, palette).
- **Modèles IA en mode "lazy load"** : ne pas charger RVM si on est sur la page Trim — un module `models.py` avec `@st.cache_resource` qui ne charge qu'à la demande.
- **Politique de données** : "tout reste local" doit être le mantra UX. Toute fonction qui envoie un fichier à une API tierce doit être clairement balisée (badge "Cloud").

---

*Document de cadrage produit — version "GIF Editor", suite à pivot.*x
