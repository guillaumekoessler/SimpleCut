# Roadmap fonctionnelle — Application Streamlit MoviePy

> Document de cadrage produit listant l'ensemble des pages Streamlit envisagées pour exposer les fonctionnalités de **MoviePy 2.x** dans une application multipage, classées par ordre d'utilité décroissant et complétées d'un tier dédié à l'augmentation par modèles d'IA.

---

## Préambule technique

### Rappels architecturaux MoviePy 2.x

L'application repose sur quatre primitives à comprendre avant toute implémentation :

- **Immutabilité des clips** : toute méthode `with_*` ou tout effet `vfx.*` / `afx.*` retourne une **copie** du clip. Cela permet en pratique de stocker dans `st.session_state` une _pile d'opérations_ (liste de transformations) et de la rejouer à la volée pour la prévisualisation, sans jamais corrompre le clip source.
- **Évaluation paresseuse** : aucun pixel n'est traité tant que `write_videofile`, `write_gif` ou `preview` n'est pas appelé. Empiler 10 effets est instantané ; le coût est concentré sur l'export final. Cela impose une UX claire avec un bouton "Exporter" distinct des contrôles de prévisualisation.
- **Numpy-first** : chaque frame est un `np.ndarray` de shape `(H, W, 3)` (et `(H, W)` pour les masques). N'importe quelle fonction Python recevant/retournant un array peut devenir un effet via `image_transform`, `time_transform` ou `transform`. Cela ouvre la porte à une intégration triviale avec OpenCV, scikit-image, et les modèles PyTorch/TensorFlow.
- **Dépendance FFmpeg** : MoviePy embarque `imageio-ffmpeg` mais l'environnement Streamlit Cloud / Docker doit le garantir. Pour le rendu de texte, MoviePy 2.x utilise désormais Pillow (et non plus ImageMagick), ce qui simplifie le déploiement.

### Conventions de l'application

- **Multipage Streamlit** : chaque cas d'usage = un fichier Python dans `pages/`.
- **Modules partagés** (`utils/`) : gestion des uploads (`tempfile.TemporaryDirectory`), génération de vignettes (`clip.save_frame`), barre de progression custom branchée sur le `logger` de MoviePy via un `proglog.ProgressBarLogger` personnalisé, mise en cache des métadonnées via `st.cache_data` (durée, fps, taille, codec).
- **Preview vs Export** : prévisualisation sur un sous-clip réduit (5–10s, fps abaissé) pour itérer vite ; export final sur la totalité avec barre de progression.
- **Téléchargement** : bouton `st.download_button` avec `mime` correctement positionné (`video/mp4`, `image/gif`, `audio/mpeg`…).

---

# 🟢 Tier 1 — MVP indispensables

> Les 6 pages qui couvrent à elles seules ~80 % des usages réels d'un outil vidéo grand public. Implémentation simple, ROI maximal.

## 1. Trim / Découpage d'un segment

**Description.** Permet d'extraire une portion temporelle précise d'une vidéo entre deux timestamps. C'est la fonction la plus universelle d'un éditeur vidéo : couper un extrait, retirer le début/fin inutile, isoler une séquence avant retraitement.

**Cas d'usage typiques.**

- Isoler les 30 secondes pertinentes d'une réunion d'1h enregistrée.
- Couper les premières secondes d'introduction d'un screencast.
- Préparer une séquence brute avant d'enchaîner sur d'autres pages (compression, GIF…).

**Fonctions MoviePy mobilisées.** `VideoFileClip(path)`, `clip.subclipped(t_start, t_end)`, `clip.write_videofile(out, codec="libx264", audio_codec="aac")`.

**UI Streamlit.**

- Upload (`st.file_uploader`, types acceptés `mp4, mov, avi, mkv, webm`).
- Affichage métadonnées (durée formatée HH:MM:SS, résolution, fps, codec, taille en MB).
- Lecteur de prévisualisation (`st.video`).
- Double slider de timestamps en secondes (`st.slider` avec `value=(0.0, duration)`), idéalement secondé par deux `st.number_input` pour saisie au centième près.
- Vignette des frames de début et fin (générées via `clip.get_frame(t)`).
- Choix codec (libx264 / libx265 / vp9), preset qualité (ultrafast → veryslow), CRF.
- Bouton "Exporter" + `st.download_button`.

**Pièges & edge cases.**

- Les timestamps acceptent `float`, `(min, sec)` ou `"HH:MM:SS.ms"` : normaliser à `float` côté UI.
- `t_end` peut être négatif (depuis la fin) — exposer cette option avec une checkbox "depuis la fin".
- Les fichiers > 200 Mo dépassent la limite par défaut Streamlit : configurer `[server] maxUploadSize` dans `config.toml`.
- Vérifier que `t_end > t_start` avant export.

**Extensions possibles.** Découpe multiple (liste de segments à concaténer), aperçu image-par-image autour des bornes pour précision frame-perfect.

---

## 2. Convertisseur Vidéo → GIF animé

**Description.** Génération de GIF animés optimisés à partir d'une portion de vidéo, avec contrôle fin sur la taille (résolution, fps, durée) pour respecter les contraintes de poids des plateformes (Slack, Discord, GitHub PR, emails).

**Cas d'usage typiques.**

- Démontrer un bug ou une feature dans une issue GitHub.
- Créer un meme depuis un extrait vidéo.
- Animation de produit pour une landing page (poids critique).

**Fonctions MoviePy mobilisées.** `clip.subclipped(t1, t2)`, `clip.with_effects([vfx.Resize(width=480)])`, `clip.write_gif(out, fps=15, program="ffmpeg")`. Optionnellement `clip.with_fps(15)` en amont.

**UI Streamlit.**

- Upload + slider de découpe (idem page 1).
- Slider de FPS (5–30, défaut 15) — c'est le levier de poids n°1.
- Slider de largeur de sortie (240, 320, 480, 640, 720, 1080) — levier n°2.
- Aperçu **estimé** du poids (calcul : `width × height × fps × duration × ratio_compression`) — UX déterminante pour éviter les exports inutiles.
- Optionnel : `vfx.AccelDecel` pour boucle douce (ramping).
- Optionnel : `vfx.TimeSymmetrize` pour effet boomerang seamless.
- Choix backend `program` : `ffmpeg` (rapide, bon par défaut) vs `imageio` (palettes + fines).

**Pièges & edge cases.**

- Le poids du GIF explose vite : afficher un warning au-delà de 10 Mo.
- Le `fps` du GIF doit être un diviseur du fps source pour éviter le tearing.
- L'export GIF est mono-thread et lent : barre de progression obligatoire.
- Couleurs limitées (256 max en GIF) : prévenir si la vidéo source est très colorée.

**Extensions possibles.** Optimisation post-export via `gifsicle`, conversion en WebP animé (meilleur compromis poids/qualité, supporté nativement par les navigateurs modernes).

---

## 3. Concaténation de plusieurs vidéos

**Description.** Assemble plusieurs clips bout à bout en une seule vidéo, avec gestion des résolutions et codecs hétérogènes. C'est la base du montage non-linéaire.

**Cas d'usage typiques.**

- Compiler plusieurs prises d'un même tournage.
- Assembler intro + corps + outro pour un YouTuber.
- Mash-up de plusieurs extraits sur un thème.

**Fonctions MoviePy mobilisées.** `concatenate_videoclips([clip1, clip2, ...], method="chain"|"compose")`, optionnellement précédé d'un `clip.with_effects([vfx.Resize(...)])` pour homogénéiser.

**UI Streamlit.**

- Upload multiple (`accept_multiple_files=True`).
- Liste réordonnable des clips (drag & drop via `streamlit-sortables`) avec vignette + durée pour chacun.
- Bouton "Inverser l'ordre" / "Trier par nom" / "Trier par durée".
- Choix de méthode :
  - `chain` (rapide, mais artefacts si tailles différentes),
  - `compose` (robuste, padding/centrage automatique sur la plus grande dimension).
- Choix de couleur de fond (utile en mode `compose`).
- Option "Normaliser à la résolution la plus basse / haute / personnalisée".
- Option "Ajouter des transitions" (renvoi vers la page Transitions du Tier 3).

**Pièges & edge cases.**

- Si fps différents, concatène mais peut produire des saccades : prévenir et proposer normalisation.
- Si certains clips n'ont pas d'audio, prévoir un `clip.with_audio(...)` muet sur les autres ou utiliser `compose`.
- Les très gros fichiers cumulés peuvent saturer la RAM lors du rendu : encourager l'export en plusieurs étapes.

**Extensions possibles.** Crossfade automatique entre chaque clip (paramètre durée global), insertion automatique d'un cartonnage noir entre clips, génération d'une chapitres YouTube basée sur les durées cumulées.

---

## 4. Compression / Redimensionnement

**Description.** Réduit le poids d'une vidéo en jouant sur la résolution, le bitrate, le codec et le fps. Cas d'usage le plus demandé en pratique : envoyer une vidéo trop lourde par mail, WhatsApp, Slack.

**Cas d'usage typiques.**

- Vidéo 4K de 500 Mo à compresser pour pièce jointe (< 25 Mo).
- Conversion d'un format ancien (`.avi`, `.mov` ProRes) vers `.mp4` H.264.
- Préparation pour intégration web (réduction agressive).

**Fonctions MoviePy mobilisées.** `vfx.Resize(width=...)` ou `(height=...)`, `clip.with_fps(...)`, et surtout les arguments fins de `write_videofile` : `bitrate`, `audio_bitrate`, `codec`, `preset`, `ffmpeg_params=["-crf", "28"]`.

**UI Streamlit.**

- Upload + métadonnées détaillées avant/après.
- Presets rapides : "Email léger" (480p, CRF 28), "Web" (720p, CRF 23), "Qualité" (1080p, CRF 18).
- Mode avancé : sliders résolution, bitrate, fps, sélection codec (libx264, libx265 = HEVC, libvpx-vp9), preset (ultrafast → veryslow).
- Estimation de la taille de sortie (basée sur `bitrate × duration / 8`).
- Comparatif visuel avant/après sur une frame fixe.

**Pièges & edge cases.**

- Le **CRF** (qualité constante) donne de meilleurs résultats que le bitrate fixe pour la plupart des cas — privilégier par défaut.
- libx265 (HEVC) compresse 30 % mieux mais est plus lent à encoder et moins universellement lu.
- Conserver le rapport d'aspect : exposer une seule dimension (l'autre est calculée).
- Vérifier les dimensions paires (codecs H.264 exigent dimensions divisibles par 2) — utiliser `vfx.EvenSize()` en filet de sécurité.

**Extensions possibles.** Mode batch (compresser un dossier entier de vidéos), export multi-qualités simultané (480/720/1080), intégration `ffprobe` pour stats détaillées avant/après.

---

## 5. Extraction de la piste audio

**Description.** Extrait l'audio d'une vidéo dans un fichier autonome (MP3, WAV, AAC, FLAC). Page minimaliste mais à fort taux d'usage.

**Cas d'usage typiques.**

- Récupérer la bande son d'une vidéo musicale.
- Extraire un podcast filmé pour publication audio-only.
- Préparer un fichier pour transcription (page IA #23).

**Fonctions MoviePy mobilisées.** `clip.audio` (un `AudioClip`), `clip.audio.write_audiofile(out, codec=..., bitrate=...)`.

**UI Streamlit.**

- Upload vidéo.
- Lecteur audio de prévisualisation (Streamlit gère `st.audio`).
- Choix format (MP3 / WAV / AAC / FLAC / OGG) — chacun avec son codec ffmpeg correspondant.
- Choix bitrate (64k, 128k, 192k, 320k pour MP3 ; lossless WAV/FLAC).
- Choix sample rate (44100 par défaut, 48000 pour vidéo, 22050 pour économie).
- Optionnel : extraire seulement un segment (sliders de découpe).
- Optionnel : application d'un `afx.AudioNormalize()` pré-export pour homogénéiser le volume.

**Pièges & edge cases.**

- Si la vidéo n'a pas d'audio (`clip.audio is None`), afficher un message clair.
- Le WAV est volumineux (1 Mo / 6 sec environ en stéréo 44.1kHz).
- Certains codecs nécessitent des extensions ffmpeg spécifiques.

**Extensions possibles.** Détection automatique des moments de silence (via `afx.AudioFadeOut` chaining et seuillage RMS) pour découpe en chapitres audio.

---

## 6. Remplacement / Ajout d'une bande son

**Description.** Remplace, ajoute, ou mixe une piste audio externe sur une vidéo existante. Indispensable pour ajouter musique de fond, voix off, ou désynchroniser intentionnellement audio et image.

**Cas d'usage typiques.**

- Ajouter une musique libre de droits sur un montage vacances.
- Coller une voix off sur un screencast muet.
- Doubler ou re-synchroniser une vidéo.

**Fonctions MoviePy mobilisées.** `AudioFileClip(path)`, `clip.with_audio(audio)`, `CompositeAudioClip([orig_audio.with_volume_scaled(0.3), new_audio])` pour mix, `afx.MultiplyVolume`, `afx.AudioFadeIn`, `afx.AudioFadeOut`, `clip.without_audio()`.

**UI Streamlit.**

- Upload vidéo + upload audio.
- Mode : "Remplacer", "Mixer", "Ajouter en surcouche à un instant T".
- Si Mixer : sliders volume vidéo originale (0–100 %) et nouvelle piste (0–200 %).
- Décalage de la piste audio (`audio.with_start(offset)`) avec slider en secondes (positif = retard, négatif = avance).
- Application optionnelle de fade-in / fade-out sur l'audio.
- Comportement si l'audio est plus court / plus long que la vidéo : "Boucler" (`afx.AudioLoop`), "Couper", "Étendre avec silence".
- Prévisualisation finale.

**Pièges & edge cases.**

- L'audio nouveau peut avoir un sample rate différent : MoviePy le rééchantillonne mais autant prévenir.
- Mode "Boucle" sur 1h de vidéo avec 30s d'audio : indiquer le nombre de boucles dans l'UI.
- En mode "Mixer", normaliser systématiquement (sinon clipping) avec `afx.AudioNormalize()`.

**Extensions possibles.** Ducking automatique (baisser la musique quand la voix off parle, via détection RMS), intégration avec les pages IA #23 (transcription) et #30 (TTS).

---

# 🔵 Tier 2 — Forte valeur ajoutée

> Pages plus élaborées en termes d'UI mais qui décuplent les capacités de l'app et couvrent des besoins fréquents.

## 7. Ajout de texte / titres

**Description.** Superpose du texte stylisé (titre, sous-titre, légende, lower-third) sur une vidéo, avec contrôle complet sur la typographie, la position et le timing d'apparition.

**Cas d'usage typiques.**

- Carton d'introduction "Vacances été 2025".
- Lower-third nominatif (interview).
- Légende de citation sur un témoignage.
- Titre de chapitre.

**Fonctions MoviePy mobilisées.** `TextClip(text, font, font_size, color, stroke_color, stroke_width, method="caption"|"label", size=(w, h), bg_color)`, `txt.with_position((x, y))` ou `("center", "bottom")`, `txt.with_start(t)`, `txt.with_duration(d)`, `CompositeVideoClip([video, txt])`. Effets de transition associés : `vfx.FadeIn`, `vfx.CrossFadeIn`, `vfx.SlideIn`.

**UI Streamlit.**

- Zone de texte multi-ligne.
- Sélecteur de police (via fichiers `.ttf` packagés dans l'app — proposer Inter, Roboto, Bebas Neue, Playfair, Pacifico, etc.).
- Slider taille de police, `st.color_picker` pour couleur texte + couleur de contour + couleur de fond (avec opacité).
- Stroke width (0 = pas de contour).
- Position : grille 3×3 (haut/centre/bas × gauche/centre/droite) + offset fin en pixels.
- Timing : `t_start`, `t_end` (ou `duration`), avec checkbox "afficher pendant toute la vidéo".
- Animation d'entrée : aucune / fade / slide-in (haut/bas/gauche/droite).
- Animation de sortie : symétrique.
- Mode `caption` (texte qui se wrap dans une box) ou `label` (taille auto).

**Pièges & edge cases.**

- Polices : nécessite que les fichiers `.ttf` soient accessibles. Embarquer un dossier `assets/fonts/` versionné.
- Texte avec accents / unicode : tester dès le début (certaines polices manquent de glyphes).
- Si `method="caption"`, il faut spécifier `size=(width, height)` sinon erreur.
- Sur clip très long, créer un `TextClip` par seconde est inefficace : générer une seule fois.

**Extensions possibles.** Templates pré-faits (titre YouTube, citation Instagram, sous-titre TikTok), animation lettre par lettre (typewriter), intégration d'emojis (police dédiée), bibliothèque de presets stylistiques sauvegardables.

---

## 8. Watermark / Logo

**Description.** Superpose un logo (PNG, idéalement transparent) ou une image de signature sur la vidéo, avec contrôle de position, taille, opacité et timing.

**Cas d'usage typiques.**

- Apposer le logo de sa chaîne sur tous les exports.
- Marquer une vidéo de démo client avant validation.
- Ajouter une signature / copyright discret.
- Watermark défensif anti-piratage.

**Fonctions MoviePy mobilisées.** `ImageClip(path)`, `logo.with_duration(clip.duration)`, `logo.with_position(("right", "bottom"))`, `logo.with_opacity(0.5)`, `logo.resized(width=120)`, `CompositeVideoClip([clip, logo])`.

**UI Streamlit.**

- Upload PNG (avec transparence) ou JPG.
- Aperçu du logo seul.
- Position : grille 9 zones (4 coins + milieux + centre).
- Offset en pixels depuis les bords (marge).
- Slider taille (% de la largeur de la vidéo, 5–30 %).
- Slider opacité (0–100 %).
- Timing : "permanent", "premières N secondes", "dernières N secondes", "intervalle" (sliders), "clignotant" (`vfx.Blink`).
- Optionnel : rotation du logo (`Rotate`).
- Mode "watermark défensif" : motif tuilé sur toute l'image avec faible opacité.

**Pièges & edge cases.**

- Si l'image n'a pas de canal alpha, le fond apparaîtra : prévenir et proposer un keying via `vfx.MaskColor`.
- Sur petit logo et vidéo 4K, attention au flou de redimensionnement.
- Exporter en H.264 perd un peu de fidélité : suggérer un PNG avec contour de sécurité.

**Extensions possibles.** Watermark animé (logo qui zoome, fade, glisse), texte de date dynamique, signature avec timestamp Exif, intégration avec un système de DRM léger.

---

## 9. Modification de la vitesse (slow-mo / accéléré)

**Description.** Modifie la vitesse de lecture du clip, soit uniformément (×0.25 à ×10), soit avec une courbe d'accélération/décélération douce. Inclut audio (pitch shift ou removal selon préférence).

**Cas d'usage typiques.**

- Ralenti dramatique sur un instant clé (×0.25 ou ×0.5).
- Accéléré pour timelapse ou montage rythmé (×4, ×10).
- Effet "satisfying" pour réseaux sociaux (rampe lente → rapide).

**Fonctions MoviePy mobilisées.** `vfx.MultiplySpeed(factor)`, `vfx.AccelDecel(new_duration, abruptness, soonness)` pour ramping, `clip.time_transform(lambda t: f(t))` pour vitesse non-linéaire custom.

**UI Streamlit.**

- Slider facteur de vitesse (0.1 à 10, log scale via `st.select_slider` avec valeurs prédéfinies).
- Toggle "Conserver l'audio" / "Couper l'audio" / "Ajuster le pitch".
- Mode avancé : `AccelDecel` avec sliders `abruptness` (-1 à 1, courbe S) et `soonness` (déplace le point d'inflexion).
- Mode "Vitesse variable" : éditeur de courbe (`streamlit-drawable-canvas` ou paramétrage par segments).
- Preview du facteur sur la durée résultante (clip 60s × 2 = 30s).

**Pièges & edge cases.**

- Audio à vitesse modifiée : par défaut MoviePy modifie aussi le pitch (effet "chipmunk"). Pour préserver le pitch, faire passer l'audio par un library externe (`pydub`, `librosa.effects.time_stretch`).
- Slow-mo sous le fps source : interpolation = saccades. Idéalement la source doit être à 60+ fps.
- Très haute vitesse (×20+) : risque de drop frames perceptible.

**Extensions possibles.** Speed ramping graphique (courbe Bezier dessinée), "speed up the boring parts" (page IA #25 couplée à détection des temps morts), interpolation de frames via modèle IA (RIFE, FILM) pour slow-mo fluide.

---

## 10. Reverse / Boomerang

**Description.** Joue la vidéo à l'envers (reverse) ou produit un effet boomerang (avant + arrière en boucle) — formats viraux par excellence sur Instagram, TikTok et BeReal.

**Cas d'usage typiques.**

- Effet "magique" (objet qui se reconstitue).
- Boomerang d'un saut, d'un toast, d'un sourire.
- Loop seamless pour story éphémère.

**Fonctions MoviePy mobilisées.** `vfx.TimeMirror()` (reverse), `vfx.TimeSymmetrize()` (boomerang = forward + reverse concat), `vfx.Loop(n=N)` pour répéter.

**UI Streamlit.**

- Toggle entre 3 modes : "Reverse complet", "Boomerang (avant + arrière)", "Boomerang inversé (arrière + avant)".
- Slider nombre de boucles (1 à 10).
- Toggle "Inverser l'audio aussi" (à utiliser avec prudence, peut être bizarre).
- Toggle "Couper l'audio" (recommandé par défaut pour boomerang).
- Optionnel : appliquer un fade très court entre les segments pour seamless.

**Pièges & edge cases.**

- L'audio reverse est généralement mauvais : couper par défaut.
- Le poids de la vidéo finale est multiplié par `2 × n_loops` : prévenir.
- Pour TikTok/Reels, exporter directement en 9:16 (cf. page 13).

**Extensions possibles.** Combinaison automatique avec page 9 (boomerang × accéléré pour effet stop-motion), génération d'un GIF directement (page 2).

---

## 11. Rotation, Flip, Crop manuel

**Description.** Manipulations géométriques de base : rotation par incréments ou angle libre, miroir horizontal/vertical, recadrage rectangulaire interactif.

**Cas d'usage typiques.**

- Vidéo filmée en portrait par erreur → rotation 90°.
- Crop pour retirer un élément gênant en bord d'image.
- Mirror pour inverser une démo gauchère/droitière.

**Fonctions MoviePy mobilisées.** `vfx.Rotate(angle, unit="deg", expand=True, bg_color=(0,0,0))`, `vfx.MirrorX()`, `vfx.MirrorY()`, `vfx.Crop(x1, y1, x2, y2)` ou `Crop(x_center, y_center, width, height)`, `vfx.Margin(margin_size, color)`.

**UI Streamlit.**

- Aperçu d'une frame pour réglages.
- Boutons rapides : ⟲ -90°, ⟳ +90°, 180°.
- Slider angle libre (-180 à 180°) avec couleur de fond pour les zones vides.
- Toggle Mirror horizontal et vertical.
- Crop interactif via `streamlit-cropper` (composant tiers idéal).
- Champs numériques x, y, width, height pour saisie précise.
- Padding (Margin) : 4 valeurs (top/right/bottom/left) + couleur, utile pour ajouter des bandes.

**Pièges & edge cases.**

- Rotation non-multiple de 90° : laisse des bandes noires aux coins, exposer `bg_color`.
- `expand=True` agrandit l'image pour ne rien couper, sinon recadre dans la boîte initiale.
- Crop avec dimensions impaires : appliquer `EvenSize` après pour compatibilité H.264.

**Extensions possibles.** Crop par ratio fixe (16:9, 9:16, 1:1, 4:5) avec snapping, redresser horizon (rotation fine), correction de perspective (via OpenCV `getPerspectiveTransform`).

---

## 12. Fade in / Fade out (vidéo + audio)

**Description.** Apparition/disparition progressive depuis/vers une couleur unie et fade audio synchronisé. Touche de polish indispensable sur tout export.

**Cas d'usage typiques.**

- Ouverture en fondu noir d'un film.
- Fermeture en fondu blanc pour effet poétique.
- Fade audio pour éviter les coupures sèches gênantes.

**Fonctions MoviePy mobilisées.** `vfx.FadeIn(duration, initial_color=(0,0,0))`, `vfx.FadeOut(duration, final_color=(0,0,0))`, `afx.AudioFadeIn(duration)`, `afx.AudioFadeOut(duration)`. Variantes : `vfx.CrossFadeIn` / `CrossFadeOut` pour transitions entre clips.

**UI Streamlit.**

- Sliders durée fade-in (0–10s) et fade-out (0–10s).
- `st.color_picker` pour couleur de fade-in et fade-out (par défaut noir).
- Toggle synchronisation audio (recommandé `True` par défaut).
- Choix de la courbe : linéaire / ease-in / ease-out (nécessite custom transform pour non-linéaire).
- Aperçu sur les premières et dernières secondes uniquement.

**Pièges & edge cases.**

- Si fade-in + fade-out > durée du clip, ils se chevauchent : avertir.
- Le fade audio est crucial pour éviter les "pops" de fin.
- Sur fond blanc, le rendu est différent (passage par valeurs hautes), réserver pour effet voulu.

**Extensions possibles.** Fade vers une image (au lieu de couleur unie), fade en cross-dissolve avec la frame finale d'un autre clip, fades multiples sur clip découpé en chapitres.

---

## 13. Reformatage pour réseaux sociaux

**Description.** Transforme une vidéo dans le format optimal d'une plateforme cible (TikTok / Reels / Shorts en 9:16, post Instagram en 1:1, YouTube en 16:9). Combine resize, crop intelligent et padding.

**Cas d'usage typiques.**

- Repurposer une vidéo YouTube horizontale en TikTok.
- Préparer une story Instagram depuis un format desktop.
- Adapter à plusieurs plateformes en un export.

**Fonctions MoviePy mobilisées.** `vfx.Resize`, `vfx.Crop`, `vfx.Margin`, `CompositeVideoClip` pour ajout de bandes (fond flou, fond couleur, fond image). Pour le fond flou : duplication du clip + `vfx.Resize` agressif + flou Gaussien (via `image_transform` + `cv2.GaussianBlur`).

**UI Streamlit.**

- Sélecteur de plateforme : TikTok (1080×1920), Reels (1080×1920), Shorts (1080×1920), Instagram Feed (1080×1080), Instagram Story (1080×1920), YouTube (1920×1080), Twitter/X (1280×720), LinkedIn (1920×1080).
- Mode de remplissage :
  - **Crop** : remplit l'écran, coupe les bords (idéal si sujet centré).
  - **Letterbox** : ajoute des bandes noires (fidélité totale).
  - **Bandes colorées** : `st.color_picker`.
  - **Fond flou** : duplique la vidéo en arrière-plan flouté (très tendance).
  - **Image de fond** : upload d'un PNG.
- Position du sujet dans le frame final (haut / centre / bas).
- Aperçu côte-à-côte avant/après.

**Pièges & edge cases.**

- Crop perd des informations : prévenir si visages détectés en zone coupée (lien vers page IA #26).
- Fond flou : coût de calcul ~2× supérieur (deux passes).
- Toujours dimensions paires.

**Extensions possibles.** Export multi-formats simultané (un upload → 3 fichiers), reframe automatique (page IA #26), templates avec barres animées top/bottom (TikTok-style).

---

# 🟣 Tier 3 — Pages créatives et différenciantes

> Pages qui apportent du fun et de la valeur de niche, à livrer une fois le socle stable.

## 14. Filtres colorimétriques

**Description.** Galerie de filtres "Instagram-like" applicables en un clic, basés sur les effets natifs MoviePy et des compositions custom.

**Cas d'usage typiques.**

- Donner un "look" cohérent à une vidéo amateur.
- Effet vintage pour vidéo de mariage.
- Noir et blanc dramatique pour court-métrage.

**Fonctions MoviePy mobilisées.** `vfx.BlackAndWhite(RGB=None, preserve_luminosity=True)`, `vfx.InvertColors()`, `vfx.LumContrast(lum=0, contrast=0, contrast_threshold=127)`, `vfx.GammaCorrection(gamma)`, `vfx.MultiplyColor(factor)`, `vfx.Painting(saturation=1.4, black=0.006)`. Pour des LUTs custom : `image_transform` + `numpy` ou OpenCV.

**UI Streamlit.**

- Galerie de presets en thumbnails (générés à la volée sur une frame représentative) :
  - Noir & blanc, Sépia, Vintage, Cold blue, Warm sunset, High contrast, Faded, Dreamy, Dramatic, Painting, Cyberpunk, Film noir.
- Mode personnalisé avec sliders : luminosité, contraste, saturation, gamma, balance des blancs (R/G/B multipliers).
- Aperçu temps réel sur frame fixe (avant export complet).
- Possibilité d'enchaîner plusieurs filtres (pile ordonnée).

**Pièges & edge cases.**

- L'application sur 60 fps × 5 minutes peut être lente : appliquer de préférence en `image_transform` (mémorisé pour ImageClip).
- LUT personnalisée 3D : nécessite OpenCV (`cv2.LUT`), à externaliser proprement.

**Extensions possibles.** Import de fichiers `.cube` (LUTs professionnelles), filtres saisonniers, filtre "deep fake style transfer" (Tier IA), histogramme avant/après.

---

## 15. Slideshow depuis images

**Description.** Crée une vidéo à partir d'une série d'images fixes, avec durée par image, transitions, et musique de fond. Outil le plus demandé pour montages photos famille/voyage.

**Cas d'usage typiques.**

- Compilation de photos de vacances en vidéo musicale.
- Présentation de portfolio créatif.
- Hommage / souvenirs avec timing musical.

**Fonctions MoviePy mobilisées.** `ImageClip(path).with_duration(d)`, `concatenate_videoclips(clips, method="compose", padding=-overlap)`, `CompositeVideoClip` pour crossfades, `AudioFileClip` pour la musique, `vfx.CrossFadeIn` / `CrossFadeOut`.

**UI Streamlit.**

- Upload multiple d'images (drag & drop, JPG/PNG).
- Liste réordonnable avec vignettes.
- Durée par image (uniforme ou individuelle).
- Type de transition entre images : aucune, crossfade, slide, fondu noir.
- Effet Ken Burns (zoom + pan progressif) → cf. page 27 du tier IA.
- Upload audio + auto-trim sur la durée totale + fades audio.
- Synchronisation possible sur les beats (cf. page IA #32).
- Format de sortie (résolution, ratio).

**Pièges & edge cases.**

- Images de tailles hétérogènes : choisir entre crop, letterbox, ou ajustement à la plus grande/petite.
- 100+ images = vidéo très longue, prévoir export progressif.

**Extensions possibles.** Templates thématiques (mariage, voyage, portfolio), texte par image (sous-titre date/lieu), mode "stop-motion" avec ImageSequenceClip à fps élevé.

---

## 16. Picture-in-picture (PiP)

**Description.** Superpose un second clip vidéo (typiquement webcam, réaction, ou commentaire) en incrustation dans une vidéo principale.

**Cas d'usage typiques.**

- Vidéo de réaction (gameplay + cam joueur).
- Tutoriel screencast + tête de l'auteur.
- Commentaire d'analyse sportive.

**Fonctions MoviePy mobilisées.** `CompositeVideoClip([main, pip.with_position(...).resized(...).with_start(...)])`. Optionnellement `with_mask` pour des coins arrondis ou forme circulaire.

**UI Streamlit.**

- Upload vidéo principale + vidéo PiP.
- Position PiP : grille 9 zones + offset.
- Taille PiP : slider (10–40 % de la largeur).
- Forme : rectangle, rectangle arrondi, cercle (via mask numpy custom).
- Bordure : épaisseur + couleur + ombre portée.
- Timing : PiP permanent, ou apparaît/disparaît à des instants T.
- Synchronisation audio : audio principal seul, audio PiP seul, mix des deux.

**Pièges & edge cases.**

- Si la PiP a une durée différente de la principale : choisir entre boucler, freeze sur dernière frame, ou disparaître.
- Le mask circulaire nécessite calcul à la main (pas d'effet natif).
- Performance : encoder une composite 1080p + 1080p PiP à 60 fps est lourd.

**Extensions possibles.** PiP avec animation d'entrée/sortie, plusieurs PiP simultanés, suivi automatique du locuteur (page IA #28), forme custom à partir d'image alpha.

---

## 17. Split-screen / Mosaïque

**Description.** Affiche 2, 3 ou 4 vidéos simultanément en grille (côte-à-côte, 2×2…) avec démarrage synchronisé ou décalé.

**Cas d'usage typiques.**

- Comparaison "before / after".
- Réaction multi-personnes (genre Family Feud).
- Démo d'un même mouvement sous différents angles (sport, danse).

**Fonctions MoviePy mobilisées.** `CompositeVideoClip` avec `with_position` et `resized` calculés selon la grille, ou `clips_array([[c1, c2], [c3, c4]])` (helper natif).

**UI Streamlit.**

- Choix layout : 1×2 (horizontal), 2×1 (vertical), 2×2 (carré), 1×3, 3×1.
- Upload des N vidéos.
- Padding/gouttière entre clips.
- Couleur de fond.
- Synchronisation : tous démarrent à 0, ou décalages individuels.
- Audio : choisir quelle source on garde, ou mix avec niveaux par piste.
- Optionnel : étiquettes (TextClip) au-dessus de chaque cellule.

**Pièges & edge cases.**

- Toutes les vidéos doivent avoir la même durée idéalement, sinon padding noir / couper la plus courte / boucler la plus courte.
- Performance : 4 streams simultanés = encodage très long.

**Extensions possibles.** Layouts non-grid (PiP combiné split-screen), animation des cellules (apparition séquentielle), grille dynamique synchronisée sur l'audio.

---

## 18. Floutage / Anonymisation

**Description.** Floute une zone fixe ou une zone qui se déplace dans le clip (suivi). Cas pro pour anonymisation RGPD ou masquage d'éléments sensibles.

**Cas d'usage typiques.**

- Flouter un visage ou une plaque d'immatriculation.
- Masquer une marque ou un logo (clip non sponsorisé).
- Protéger un mineur ou un témoin sur une vidéo journalistique.

**Fonctions MoviePy mobilisées.** `vfx.HeadBlur(fx, fy, radius)` pour un flou suivant une trajectoire (`fx`, `fy` = fonctions du temps), ou implémentation custom via `image_transform` + `cv2.GaussianBlur` sur une région définie.

**UI Streamlit.**

- Aperçu avec sélection de zone (rectangle) sur première frame.
- Slider rayon de flou (5–100 px).
- Mode flou : Gaussien, mosaïque (pixelisation), couleur unie, emoji.
- Type de zone : fixe, ou trajectoire linéaire entre 2 points clés (interpolation), ou multiples keyframes.
- Suivi automatique : option qui renvoie vers page IA #28 (object tracking).
- Multiple zones simultanées (liste de masques).

**Pièges & edge cases.**

- Sur visage en mouvement, le flou fixe rate la cible : nécessité d'un tracking.
- Un floutage trop léger reste réversible : utiliser pixelisation ou occultation totale pour anonymisation sérieuse.

**Extensions possibles.** Détection automatique des visages (page IA #27), détection automatique des plaques (modèle YOLO custom), masque de forme libre dessiné à la souris.

---

## 19. Sous-titres depuis fichier .srt

**Description.** Charge un fichier `.srt` ou `.vtt` et incruste les sous-titres synchronisés sur la vidéo (sous-titres dits "burned-in" / "open captions").

**Cas d'usage typiques.**

- Sous-titrer une vidéo pour réseaux sociaux (95 % des vues sont sans son).
- Accessibilité (sourds et malentendants).
- Traduction visible.

**Fonctions MoviePy mobilisées.** `from moviepy.video.tools.subtitles import SubtitlesClip`, `SubtitlesClip(srt_path, make_textclip=lambda text: TextClip(text, ...))`, `CompositeVideoClip([video, subs.with_position(("center", "bottom"))])`.

**UI Streamlit.**

- Upload `.srt` ou `.vtt`.
- Aperçu textuel parsé du fichier.
- Tous les contrôles de la page 7 (police, taille, couleur, contour, fond).
- Position : slider vertical pour réglage fin (les sous-titres sont presque toujours en bas).
- Optionnel : édition inline des cues (corriger une faute) avant rendu.
- Mode "auto-générer depuis l'audio" → renvoi page IA #23 (Whisper).

**Pièges & edge cases.**

- Les `.srt` ont des encodages variables (UTF-8 BOM, latin-1) : auto-détecter avec `chardet`.
- Lignes très longues : prévoir wrap automatique.
- Synchronisation : si la vidéo est trimmée, les timestamps SRT sont décalés — recalculer.

**Extensions possibles.** Multi-langues (deux pistes simultanées), styles karaoké (mot-par-mot surligné), animations word-by-word (TikTok-style), export `.ass` avec styles avancés.

---

## 20. Transitions entre clips

**Description.** Insère automatiquement des transitions soignées entre clips concaténés (cross-dissolve, slide, fondu via couleur).

**Cas d'usage typiques.**

- Adoucir les coupures d'un montage de vacances.
- Effet "swipe" entre scènes d'un vlog.
- Fondu enchaîné cinématographique.

**Fonctions MoviePy mobilisées.** `vfx.CrossFadeIn(d)`, `vfx.CrossFadeOut(d)`, `vfx.SlideIn(d, side)`, `vfx.SlideOut(d, side)`. Pour assembler : `CompositeVideoClip` avec décalages temporels ou concat avec `padding=-overlap`.

**UI Streamlit.**

- Liste des clips (cf. page 3).
- Type de transition globale, ou par paire de clips.
- Durée de la transition (0.3–2s typique).
- Side (pour slides) : left, right, top, bottom.
- Aperçu de la jonction sur quelques secondes autour du raccord.

**Pièges & edge cases.**

- CrossFade nécessite que les clips se chevauchent dans le temps de composition : gérer les offsets.
- Trop long = mou ; trop court = peu visible.

**Extensions possibles.** Bibliothèque de transitions custom (zoom, glitch, pixelate, fond noir), transitions sur le beat (page IA #32), wipe avec masque animé.

---

## 21. Boucle parfaite (seamless loop)

**Description.** Transforme un clip en une boucle qui se répète indéfiniment sans coupure visible. Utile pour fonds animés, écrans d'attente, art numérique.

**Cas d'usage typiques.**

- Background vidéo d'un site web.
- Fond animé de visioconférence.
- Œuvre vidéo de loop art.

**Fonctions MoviePy mobilisées.** `vfx.MakeLoopable(overlap_duration)` (fait fondre la fin sur le début), `vfx.Loop(n=N)` ou `vfx.Loop(duration=D)` pour répéter, `vfx.TimeSymmetrize` (alternative pour boucle palindromique).

**UI Streamlit.**

- Slider durée de l'overlap (0.5–3s) — c'est la longueur sur laquelle la fin se mélange au début.
- Slider nombre de boucles ou durée totale cible.
- Choix entre `MakeLoopable` (fondu enchaîné) et `TimeSymmetrize` (aller-retour).
- Aperçu spécifique sur la jonction fin → début pour valider la fluidité.

**Pièges & edge cases.**

- L'overlap réduit la durée perçue du clip d'autant.
- Audio : généralement on coupe pour boucle visuelle pure.

**Extensions possibles.** Détection automatique du "meilleur" point de boucle (analyse de similarité de frames), génération de boucle infinie en WebM/AV1 pour intégration web légère.

---

## 22. Génération de générique

**Description.** Crée un générique de fin (ou de début) défilant verticalement, à partir d'un fichier texte structuré (rôles + noms).

**Cas d'usage typiques.**

- Générique de fin de court-métrage.
- Liste des contributeurs d'un projet associatif.
- Générique stylisé d'introduction.

**Fonctions MoviePy mobilisées.** `from moviepy.video.tools.credits import CreditsClip`, `CreditsClip(credit_file, width=720, color="white", stroke_color="black", stroke_width=2, font="Arial-Bold", fontsize=60, gap=0)`, ensuite combiner avec `Scroll` pour défilement, ou `with_position(lambda t: ...)` pour scroll vertical.

**UI Streamlit.**

- Saisie d'un texte structuré (format MoviePy : `..` pour titre, `.blank N` pour espace, lignes `Role .. Name`).
- Éditeur visuel ligne par ligne (ajouter rôle / personne) → généré automatiquement.
- Tous les contrôles de la page 7 (police, couleur…).
- Vitesse de défilement (px/s).
- Couleur ou image de fond.
- Bande son (musique de générique).

**Pièges & edge cases.**

- Format CreditsClip strict, à valider avant rendu.
- Sur défilement très long, durée de la vidéo finale = `(text_height + screen_height) / speed`.

**Extensions possibles.** Templates Hollywood (avec logo studio), génériques horizontaux (style Star Wars par scroll incliné via perspective), import depuis CSV/Google Sheets.

---

# 🤖 Tier IA — Édition vidéo augmentée par modèles d'intelligence artificielle

> Pages qui combinent MoviePy avec des modèles d'IA modernes pour offrir des fonctionnalités impossibles à faire en pur DSP. Ces pages sont les plus différenciantes mais demandent une infrastructure plus lourde (GPU pour certains, API externes pour d'autres).

**Notes d'architecture transverses.**

- Privilégier les modèles **petits / quantifiés** lorsque c'est possible (faster-whisper, ONNX, MediaPipe) pour rester déployable sans GPU.
- Pour les modèles lourds (génération vidéo, music gen, super-résolution) : exposer un toggle "API externe" (Replicate, Hugging Face Inference, Anthropic, OpenAI) ou "local GPU".
- Toujours afficher un avertissement explicite quand un upload est envoyé à un service tiers (RGPD).
- Mettre en cache agressivement les sorties des modèles sur le hash du fichier d'entrée + paramètres.

---

## 23. Transcription automatique et sous-titrage (Whisper)

**Description.** Génère automatiquement les sous-titres d'une vidéo à partir de sa piste audio en utilisant Whisper. Sortie en `.srt` éditable et incrustation directe dans la vidéo.

**Cas d'usage typiques.**

- Sous-titrer rapidement une vidéo TikTok / Reel.
- Générer une transcription complète d'un podcast filmé.
- Première étape avant traduction automatique (page #24).

**Stack technique.** `faster-whisper` (CTranslate2, 4× plus rapide que Whisper officiel, modèles `tiny` à `large-v3`), ou API OpenAI Whisper, ou Whisper.cpp pour CPU pur. Pipeline : `clip.audio.write_audiofile(temp_wav)` → `model.transcribe(temp_wav, language="fr", word_timestamps=True)` → conversion en `SubtitlesClip` → composite.

**UI Streamlit.**

- Choix du modèle (tiny rapide / base équilibré / small recommandé / medium / large-v3 précis).
- Choix de la langue (auto-détection ou forcée).
- Option "diarisation" (qui parle quand) via `pyannote.audio`.
- Édition manuelle des cues générés dans un tableau `st.data_editor`.
- Mode "karaoké" (mot par mot surligné) grâce aux `word_timestamps`.
- Tous les contrôles de style (page 7 et 19).
- Export : `.srt` seul, `.vtt`, ou vidéo avec sous-titres incrustés.

**Pièges & edge cases.**

- Whisper hallucine sur des silences ou musique : prévoir VAD (`silero-vad`) en pré-traitement.
- Modèle `large` requiert 10 Go VRAM minimum.
- Coût API OpenAI : ~0.006 $ / minute audio.

**Extensions possibles.** Génération multi-langues simultanée, summarization du transcript par LLM, export SRT bilingue (page #24).

---

## 24. Traduction automatique des sous-titres

**Description.** Traduit un fichier de sous-titres existant ou auto-généré dans une autre langue, en conservant la synchronisation. Réincruste les sous-titres traduits dans la vidéo.

**Cas d'usage typiques.**

- Localiser une vidéo française pour audience anglophone.
- Sous-titrer un podcast étranger en français.
- Sous-titres bilingues (deux pistes superposées).

**Stack technique.** API LLM (Claude, GPT-4, Gemini) avec prompt context-aware, ou modèles dédiés (`facebook/nllb-200`, `Helsinki-NLP/opus-mt-*` via Transformers). Le LLM est généralement supérieur en qualité contextuelle.

**UI Streamlit.**

- Upload `.srt` ou utilisation directe de la sortie page #23.
- Langue source (auto-détectée) + langue cible.
- Choix moteur : Claude (Anthropic), GPT-4, Gemini, NLLB local.
- Option "bilingue" : afficher original + traduction sur 2 lignes.
- Édition manuelle après traduction.
- Aperçu côte-à-côte source / cible.

**Pièges & edge cases.**

- Le LLM doit recevoir le contexte (cues précédentes/suivantes) pour cohérence — découper en batch avec overlap.
- Préserver les caractères de timing du SRT (ne pas que le LLM les modifie).
- Idiomes / argot : qualité variable selon langue cible.

**Extensions possibles.** Doublage vocal de la traduction (chaînage avec page #30 TTS), adaptation culturelle par LLM (pas seulement traduction), validation par modèle "back-translation" pour QA.

---

## 25. Auto-highlights / résumé vidéo intelligent

**Description.** Identifie automatiquement les moments les plus intéressants d'une vidéo longue (réunion, podcast, conférence) et génère un résumé vidéo court.

**Cas d'usage typiques.**

- Compiler un "best of" de 5 min depuis un live Twitch d'1h.
- Résumé exécutif d'une réunion d'1h en 2 min.
- Générer des shorts depuis un long-format YouTube.

**Stack technique.** Pipeline en 3 étapes :

1. Transcription (page #23) avec timestamps.
2. LLM analyse le transcript pour identifier les segments saillants (`[(t_start, t_end, importance_score)]`).
3. MoviePy assemble les segments via `concatenate_videoclips` avec `CrossFadeIn/Out`.

Alternative : modèles de "video summarization" type CLIP-based qui scorent les frames sur saillance visuelle (`pytorchvideo`, `decord`).

**UI Streamlit.**

- Upload vidéo + paramètre "durée cible" (slider 30s à 10 min).
- Option "type de résumé" : moments forts (LLM), moments visuellement saillants (CLIP), changements de scène (PySceneDetect).
- Pour LLM : prompt configurable (ex: "garde uniquement les moments où on parle de X").
- Aperçu segments sélectionnés avant assemblage final.
- Édition : ajouter/retirer manuellement des segments candidats.

**Pièges & edge cases.**

- LLM voit transcript, pas vidéo : un moment visuellement clé sans parole sera raté → coupler les deux signaux.
- Coupures abruptes au milieu d'une phrase : utiliser les `word_timestamps` Whisper pour couper sur fin de phrase.

**Extensions possibles.** Génération automatique de N "shorts" vertical depuis un long horizontal (combine avec page #26), génération d'un titre + description du résumé par LLM, chapitrage YouTube auto.

---

## 26. Reframe intelligent (smart 9:16)

**Description.** Convertit une vidéo horizontale (16:9) en vertical (9:16) en gardant **automatiquement** le sujet principal au centre du cadre via détection et tracking.

**Cas d'usage typiques.**

- Repurposer une interview YouTube en TikTok sans perdre le visage.
- Adapter du contenu sportif horizontal en story.
- Créer des Shorts à partir d'un long-format.

**Stack technique.** Détection de saillance (modèle `pytorch_saliency`, `BASNet`, `U2-Net`) ou détection visage/personne (`MediaPipe`, `YOLOv8-pose`). À chaque frame on calcule un point d'intérêt → on lisse la trajectoire (filtre passe-bas pour éviter le tremblement) → on `Crop` dynamique via `clip.transform(smart_crop_function)`.

**UI Streamlit.**

- Upload vidéo + format cible.
- Choix algorithme : détection visages, détection personnes, saillance générique, mode hybride.
- Slider "réactivité" du tracking (lissage temporel).
- Toggle "garder plusieurs sujets" (le crop devient un compromis ou le format devient split-screen).
- Aperçu de la trajectoire de crop sur quelques frames.

**Pièges & edge cases.**

- Tremblement du crop : appliquer un filtre Kalman ou exponentiel.
- Plusieurs sujets : dilemme algorithmique (suivre le plus grand, le plus parlant — coupler audio).
- Sujet sortant du cadre source : impossible à récupérer.

**Extensions possibles.** Mode "actif" qui suit le speaker (couplé à la détection de bouche qui bouge), mode "match-cut" qui change de sujet sur transitions audio, génération de plusieurs shorts ciblés sur différents sujets.

---

## 27. Détection de visages + floutage automatique

**Description.** Détecte automatiquement tous les visages dans la vidéo et applique un floutage / pixelisation pour anonymisation totale, sans intervention manuelle.

**Cas d'usage typiques.**

- Anonymisation conformité RGPD pour journalisme / étude.
- Protection de mineurs sur une vidéo publique.
- Enquête policière / juridique nécessitant occultation.

**Stack technique.** `RetinaFace`, `MediaPipe Face Detection`, ou `YOLOv8-face` pour détection frame-par-frame. Pour la cohérence temporelle : tracker (DeepSORT, ByteTrack). Application du flou : `image_transform` avec masque circulaire et `cv2.GaussianBlur` ou pixelisation par downscale + upscale nearest.

**UI Streamlit.**

- Upload vidéo.
- Choix du modèle de détection (vitesse vs précision).
- Type de masquage : flou Gaussien, mosaïque, ovale noir, emoji 😀.
- Slider seuil de confiance détection.
- Toggle "Conserver certains visages" : pré-scan qui liste tous les visages uniques (clustering embeddings) → l'utilisateur coche ceux à NE PAS flouter.
- Padding autour du visage (le flou doit dépasser un peu).

**Pièges & edge cases.**

- Détection rate parfois 1 frame sur N : interpoler entre frames adjacentes ou utiliser un tracker.
- Performance : ~5–20 fps en CPU, temps réel en GPU.
- Visages partiels (de profil, de dos, masqués) souvent ratés.

**Extensions possibles.** Détection de plaques d'immatriculation (modèle dédié ALPR), de tatouages, de logos de marques, de texte (`EasyOCR` + flou).

---

## 28. Suppression / remplacement d'arrière-plan (chroma IA)

**Description.** Sépare automatiquement le sujet du fond sans nécessiter de fond vert, puis permet de remplacer l'arrière-plan par une image, vidéo, ou fond uni.

**Cas d'usage typiques.**

- Remplacer le fond d'une visioconférence enregistrée.
- Effet "studio" sur une vidéo tournée chez soi.
- Compositing créatif (sujet sur fond fictif).

**Stack technique.** Modèles de matting / segmentation : `RobustVideoMatting (RVM)`, `BackgroundMattingV2`, `BiRefNet`, `SAM 2` (Segment Anything Model v2 de Meta) pour précision haut de gamme. Sortie = clip avec masque alpha → `clip.with_mask(mask_clip)` puis `CompositeVideoClip([new_bg, fg])`.

**UI Streamlit.**

- Upload vidéo source + (optionnel) upload nouveau fond (image ou vidéo).
- Si pas de nouveau fond : choix de couleur unie ou flou du fond original.
- Choix modèle (qualité vs vitesse).
- Slider "tolérance" et "feathering" des bords.
- Aperçu du masque seul (utile pour debug).

**Pièges & edge cases.**

- Cheveux fins, transparence, mouvement rapide : qualité de matting variable.
- Coût GPU élevé pour modèles haut de gamme : prévoir mode "API externe".
- Cohérence temporelle (flicker du masque entre frames) : RVM est conçu pour la vidéo, BiRefNet est image-based donc plus instable.

**Extensions possibles.** Effet "portrait mode" (fond légèrement flou, sujet net), green-screen virtuel (fond uni en sortie pour réutilisation downstream), chaînage avec PiP (sujet détouré incrusté).

---

## 29. Génération de B-roll par IA

**Description.** Génère des plans d'illustration (B-roll) à partir de prompts textuels et les insère dans le montage. L'utilisateur écrit "un drone qui survole une forêt en automne", un modèle de génération vidéo produit le clip, MoviePy l'incruste.

**Cas d'usage typiques.**

- Illustrer un podcast filmé avec des plans de coupe stylisés.
- Combler des manques visuels d'un montage.
- Créer des vidéos documentaires sans matériel de tournage.

**Stack technique.** Modèles text-to-video : `Stable Video Diffusion (SVD)`, `AnimateDiff`, `CogVideoX`, `LTX-Video`, ou via API (Runway Gen-3, Pika Labs, Sora API quand dispo, Kling). Pour image-to-video : `SVD` est très bon. MoviePy fait l'assemblage : `concatenate_videoclips`, `CrossFadeIn/Out`.

**UI Streamlit.**

- Liste de "trous" identifiés dans le montage (manuel ou via analyse du transcript page #25).
- Pour chaque trou : prompt textuel + durée souhaitée + style (cinematic / cartoon / réaliste).
- Choix du moteur (local vs API).
- Génération + aperçu + régénération si besoin.
- Insertion automatique aux bons timestamps avec transitions.

**Pièges & edge cases.**

- Génération vidéo coûteuse (1$/clip côté API, plusieurs minutes en local).
- Cohérence stylistique entre clips générés et clip original difficile à garantir.
- Question éthique : signaler explicitement les contenus synthétiques.

**Extensions possibles.** Génération à partir d'images existantes (image-to-video sur photos perso), continuité narrative (passer le frame finale comme image conditionnante du prompt suivant), watermark "AI Generated" forcé.

---

## 30. Voix off TTS (Text-to-Speech)

**Description.** Génère une voix off à partir d'un texte écrit, avec possibilité de cloner une voix existante. La piste générée est synchronisée et incrustée sur la vidéo.

**Cas d'usage typiques.**

- Doublage rapide d'une vidéo muette.
- Narration de tutoriels.
- Voix off de pub à la chaîne.
- Localisation post-traduction (chaînage page #24).

**Stack technique.** TTS modernes : `Coqui XTTS-v2` (multi-langue, voice cloning depuis 6s), `Bark`, `ElevenLabs API` (qualité top), `OpenAI TTS API`, `F5-TTS`. Sortie = WAV → `AudioFileClip` → `CompositeAudioClip` ou `with_audio` selon mix souhaité.

**UI Streamlit.**

- Saisie texte (avec ponctuation, qui influence le ton).
- Choix de voix (preset ou upload échantillon de 10s pour cloning).
- Choix langue.
- Réglages prosodie : vitesse, pitch, pauses.
- Mode "synchroniser sur la vidéo" : génère par chunks correspondant à des timestamps du transcript.
- Mix avec audio original (ducking auto si voix s'ajoute).

**Pièges & edge cases.**

- Voice cloning soulève des questions de consentement : obligation légale d'avertissement.
- Hallucinations possibles (mots inventés).
- Synchronisation labiale impossible sans modèle dédié (cf. page #34 si ajoutée plus tard).

**Extensions possibles.** Lip-sync (Wav2Lip, SadTalker) pour adapter les lèvres à la voix générée, voix multiples pour dialogue, intégration "podcast clip" (générer un podcast à partir d'un article).

---

## 31. Génération de musique de fond par IA

**Description.** Génère une piste musicale originale et libre de droits à partir d'un prompt textuel ("ambient electronic, 90 BPM, calm and uplifting") et l'intègre comme bande son.

**Cas d'usage typiques.**

- Musique de fond pour un montage de vacances sans risque de copyright strike.
- Bande son d'un teaser / pub sans licence.
- Musique d'ambiance personnalisée pour podcast.

**Stack technique.** `MusicGen` (Meta AudioCraft), `Stable Audio`, `Suno API`, `Udio API`. Sortie WAV stéréo → `AudioFileClip` → mix avec audio existant via `CompositeAudioClip` et `MultiplyVolume`.

**UI Streamlit.**

- Prompt textuel + sliders (durée, BPM, énergie 0–10, ambiance).
- Choix du modèle.
- Génération + écoute + régénération.
- Ducking automatique si voix présente (analyse RMS du voiceover original).
- Bouclage automatique si la durée demandée dépasse celle de la génération unique (généralement 30s).

**Pièges & edge cases.**

- Génération > 30s : qualité décroît, préférer génération de 30s + `MakeLoopable`.
- Cohérence stylistique sur générations multiples : difficile.
- Licence : variable selon modèle (MusicGen permissif, Suno restrictif).

**Extensions possibles.** Synchronisation des cuts vidéo sur les beats détectés (`librosa.beat.beat_track`), passage du transcript au LLM qui génère le prompt musical adéquat, transitions musicales entre scènes.

---

## 32. Synchronisation des coupes sur le rythme musical

**Description.** Détecte automatiquement les beats d'une piste musicale et coupe la vidéo (changements de plan, cuts, effets) sur les beats. Effet "music video" instantané.

**Cas d'usage typiques.**

- Montage rythmé de vacances / sport / vlog.
- Compilation sportive sur musique tendance.
- Edit TikTok / Instagram synchronisé.

**Stack technique.** `librosa.beat.beat_track(y, sr)` → liste de timestamps des beats. Algo : découper la vidéo source en N segments aléatoires de durées variables, choisir lesquels conserver, et caler chaque cut sur un beat (resize temporel via `MultiplySpeed` ou simplement `subclipped`). `concatenate_videoclips` final.

**UI Streamlit.**

- Upload vidéo + audio musical (ou réutilisation page #31).
- Visualisation forme d'onde + beats détectés (matplotlib ou plotly).
- Slider sensibilité de détection (`tightness` librosa).
- Mode : cut sur chaque beat / sur 1 beat sur 2 / sur les downbeats uniquement.
- Choix de la stratégie de sélection de segments source (aléatoire, ordre chronologique, par énergie visuelle).
- Aperçu avant export.

**Pièges & edge cases.**

- Musique sans rythme clair (ambient, classique) : détection peu fiable.
- Si les segments source sont plus courts qu'un beat-to-beat : padding ou suppression.

**Extensions possibles.** Effets visuels sur le beat (zoom punch, flash blanc, glitch), match cut intelligent (transition basée sur similarité de frames couplée au beat), génération multi-versions (lente / rapide / hype).

---

## 33. Amélioration audio par IA (denoising, voice isolation)

**Description.** Nettoie une piste audio bruyante : suppression des bruits de fond (vent, climatisation, foule), isolation de la voix, amélioration de la clarté.

**Cas d'usage typiques.**

- Vidéo d'interview tournée en extérieur venteux.
- Visioconférence enregistrée avec bruits parasites.
- Récupération d'un dictaphone bas de gamme.

**Stack technique.** `Demucs` (Meta) pour séparation vocal/instruments/bruits, `RNNoise` pour denoising léger, `DeepFilterNet` pour denoising temps réel, `Resemble Enhance` ou `Adobe Enhance API` pour upscaling vocal. Pipeline : extraction audio → denoising → réinjection via `clip.with_audio`.

**UI Streamlit.**

- Upload vidéo (ou audio standalone).
- Choix du modèle (qualité vs vitesse).
- Mode : "supprimer le bruit", "isoler la voix", "isoler la musique", "séparer toutes les sources" (4 stems Demucs).
- Slider intensité (0–100 %).
- Aperçu A/B (avant / après) avec switch instantané.

**Pièges & edge cases.**

- Sur audio très dégradé, le modèle peut introduire des artefacts (effet "sous-marin").
- Démucs lourd (~10 Go RAM, GPU recommandé pour temps raisonnable).

**Extensions possibles.** Re-mastering complet (compression, EQ, normalisation auto), changement de "scène acoustique" (passer d'un enregistrement extérieur à un studio), restauration audio vintage.

---

## 34. Style transfer / filtres neuronaux

**Description.** Applique le style visuel d'une référence (peinture, photo, film) sur l'ensemble de la vidéo via un modèle de neural style transfer ou un modèle vidéo génératif image-to-image.

**Cas d'usage typiques.**

- Convertir une vidéo réelle en style "Van Gogh" / "Studio Ghibli" / "Cyberpunk".
- Animation stylisée à partir d'un live action.
- Effets artistiques pour clip musical.

**Stack technique.** Modèles : `AnimateDiff` avec ControlNet pour conditionnement temporel, `CoTracker` + `Stable Diffusion img2img` frame par frame, modèles dédiés vidéo style transfer (`Rerender A Video`, `TokenFlow`, `EbSynth` semi-auto). Application via `image_transform` ou pipeline batch frame-par-frame, puis recompose en vidéo.

**UI Streamlit.**

- Upload vidéo + image de référence du style.
- Choix du modèle (Ghibli, Pixar, oil painting, comic, anime via LoRA pré-entraînés).
- Slider "force" du style (0–100 %).
- Cohérence temporelle : option "haute" (plus lent, moins de flicker) ou "basse" (plus rapide).
- Aperçu sur quelques frames avant rendu complet.

**Pièges & edge cases.**

- Coût compute énorme (style transfer image-par-image sur vidéo 30s à 30 fps = 900 inférences).
- Flicker temporel : le défi principal — sans modèle vidéo-natif, on l'obtient à coup sûr.
- Préférer API cloud sauf grosse infra GPU.

**Extensions possibles.** Style transfer partiel (juste sur le sujet via masque), animation depuis photos fixes (live photos générées), face stylization spécifique.

---

## 35. Génération de thumbnail / poster

**Description.** Sélectionne automatiquement la meilleure frame de la vidéo (visuellement attractive, expressive) et la décore avec titre, image, effets pour servir de miniature YouTube ou de poster.

**Cas d'usage typiques.**

- Miniature YouTube optimisée CTR.
- Poster pour partage social.
- Frame d'introduction d'un article.

**Stack technique.** Sélection de frame :

- Score esthétique via `LAION-Aesthetic Predictor` ou `MUSIQ`,
- Detection de visage souriant / expression forte (`FER`),
- Diversité de couleurs / contraste (heuristiques `numpy`).

Décoration : MoviePy en mode `ImageClip` + `TextClip` sauvegardé en PNG via `clip.save_frame`. LLM pour suggérer un titre accrocheur basé sur le transcript.

**UI Streamlit.**

- Upload vidéo.
- Top N frames candidates avec score esthétique (galerie cliquable).
- Génération automatique de titres (LLM sur le transcript) — 5 propositions.
- Templates de thumbnail (style YouTube : grand titre, flèche, encadré visage zoomé).
- Export PNG/JPG haute résolution.

**Pièges & edge cases.**

- Score esthétique peu fiable sur certains contenus (technique, abstract).
- Droit à l'image : flouter automatiquement si visages non-consentis (page #27).

**Extensions possibles.** A/B testing automatique (générer 5 variantes, demander à l'utilisateur sa préférée), génération du titre + thumbnail par un seul LLM multimodal (Claude, GPT-4o), templates spécifiques par plateforme.

---

## 36. Modération automatique du contenu

**Description.** Analyse la vidéo pour détecter des contenus problématiques (nudité, violence, langage explicite, drogues) et propose des actions automatiques (flou, mute, suppression du segment).

**Cas d'usage typiques.**

- Préparer une vidéo amateur pour publication grand public / familiale.
- Conformité plateforme (YouTube Kids).
- Modération en pre-publication pour communautés.

**Stack technique.**

- Visuel : modèles NSFW (`opennsfw2`, `Falconsai/nsfw_image_detection`), violence (`Hateful Memes`), classifieurs CLIP avec prompts custom.
- Audio : transcript Whisper → LLM pour détection langage offensant, ou modèles spécifiques (`unitary/toxic-bert`).
- Application MoviePy : `vfx.HeadBlur` ou pixelisation sur zones problématiques, `afx.MultiplyVolume(0)` ou bip de censure sur segments audio offensants.

**UI Streamlit.**

- Upload vidéo.
- Choix des catégories à détecter (cases à cocher).
- Seuils de sensibilité par catégorie.
- Rapport détaillé : timeline avec markers colorés sur les segments détectés.
- Pour chaque détection : action proposée (flou / mute / coupe / ignorer).
- Validation manuelle avant export.

**Pièges & edge cases.**

- Faux positifs fréquents (anatomie médicale, films de guerre légitimes).
- Modèles NSFW peuvent avoir des biais culturels.
- Toujours laisser le contrôle final à l'humain.

**Extensions possibles.** Conformité multi-plateformes (règles YouTube vs TikTok vs Twitter), génération automatique d'un rapport PDF de modération, modération des sous-titres (anonymisation des noms propres).

---

# 📋 Synthèse de priorisation

| Tier       | Pages | Effort UI   | Effort technique | Valeur utilisateur        |
| ---------- | ----- | ----------- | ---------------- | ------------------------- |
| 🟢 Tier 1  | 6     | Faible      | Faible           | Très élevée               |
| 🔵 Tier 2  | 7     | Moyen       | Moyen            | Élevée                    |
| 🟣 Tier 3  | 9     | Moyen-élevé | Moyen            | Moyenne à élevée          |
| 🤖 Tier IA | 14    | Élevé       | Élevé (GPU/API)  | Très élevée mais coûteuse |

**Recommandation de roadmap.**

1. **Sprint 1–2** : Tier 1 complet + module commun (uploads, preview, cache, progress). C'est le MVP livrable.
2. **Sprint 3–4** : Pages 7, 9, 10, 13 du Tier 2 (couvrent les besoins les plus exprimés).
3. **Sprint 5** : Pages 11, 12 + une première IA très impactante : **page #23 (Whisper)** qui transforme l'app.
4. **Sprint 6+** : Tier 3 par ordre d'intérêt utilisateur, et IA une à une selon la traction (commencer par #23, #26, #27 qui sont les plus immédiates et déployables sans GPU lourd via API).

**Points d'attention transverses dès le début :**

- Architecture multipage avec un `state` partagé bien pensé (clip courant, opérations empilées).
- Système de plugins / "operations" (chaque effet = une classe sérialisable) pour permettre demain une vraie timeline éditable.
- Internationalisation FR/EN dès le début (les strings UI dans des dictionnaires).
- Logging et observabilité (durée des renders, modèles utilisés, erreurs FFmpeg).
- Politique claire sur les données envoyées à des APIs tierces (RGPD).

---

_Document de cadrage produit — version initiale._
