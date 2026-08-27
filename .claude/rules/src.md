---
paths:
  - "src/**"
---

# Doctrine du code applicatif

Ce qui casse si on l'ignore. Le détail — mesures, alternatives écartées, chiffres —
vit dans la docstring du module cité. Aucune valeur de réglage n'est recopiée ici :
seulement le nom de la constante qui la porte.

## Conversion GIF

- **Une seule palette pour tout le GIF**, jamais une par image. Une palette
  recalculée image par image fait pulser les couleurs et empêche l'encodeur de ne
  réécrire que le rectangle modifié d'une image à la suivante. Le nombre de
  couleurs, la méthode de quantification et son affinage sont des réglages de
  `utils/GifPalette.py` : s'y référer, ne pas les redécider ailleurs.
- **Aucun tramage.** LZW, seule compression du format, ne compresse que des suites
  d'index identiques, et le tramage les détruit toutes. `dither=NONE` est écrit
  explicitement partout : cette valeur ne doit jamais retomber dans un défaut de
  bibliothèque.
- **La cadence sort de `FPS_EXACTS`.** Le format stocke le délai d'affichage en
  centièmes de seconde : une cadence dont le délai n'est pas un multiple entier de
  10 ms donne un GIF qui ne joue pas à la vitesse demandée.
- **On ne propose jamais plus que la source.** Les catalogues de vitesses et de
  largeurs sont calculés depuis la vidéo importée : ni image inventée, ni
  agrandissement.
- **`ConversionParams.dimensions_sortie` décide seul des dimensions de sortie.**
  L'export redimensionne, le panneau estime le pic mémoire, la page annonce la
  taille : les trois appellent cette méthode. Un calcul parallèle rendrait
  l'annonce fausse dès qu'une source sort du cas nominal.
- **On n'appelle pas `clip.write_gif`.** La boucle d'encodage est pilotée par
  `utils/GifExport.py` pour que l'attente reste rapportable ; toute progression
  passe par son `Rapporteur` et ses `Phase`.
- **`convertir_en_gif` est propriétaire de son fichier de sortie** : en cas
  d'échec il l'efface, y compris si l'appelant l'avait créé. Rien à nettoyer
  derrière lui.
- **L'identité d'un GIF est le couple (identité de la vidéo, paramètres).**
  L'affichage est une fonction de cette identité et du cache, jamais une
  conséquence du clic. C'est ce qui fait qu'un rerun ne perd pas l'aperçu et qu'un
  retour aux réglages précédents ne regénère rien.

## Affichage des médias

- **Le calage ne dépend que du ratio du média**, jamais de sa taille absolue, et
  il est calculé par `utils/Layout.py`. Ne jamais écrire un `st.columns` de
  centrage à la main dans une page.
- **`colonne_media` pour une vidéo, `colonne_image` pour une image.** La première
  émet une règle CSS **globale** figeant le ratio des `<video>` ; l'employer pour
  afficher un GIF écraserait le ratio de l'aperçu vidéo de la page.
- **Un instant de vignette passe toujours par `temps_vignette`** avant d'atteindre
  le cache d'extraction : il arrondit — donc stabilise la clé de cache — et borne
  la demande avant la dernière image du fichier.
- **`st.video` tronque `start_time` / `end_time` à la seconde entière** : les
  bornes de boucle viennent de `bornes_boucle_video`, qui englobe la sélection
  plutôt que de l'amputer.

## Streamlit

- Une page qui a besoin de la vidéo vérifie sa présence et s'arrête (`st.stop()`)
  au lieu de laisser la suite planter.
- Isoler dans un `@st.fragment` toute zone dont un widget ne doit pas relancer la
  page entière : un rerun global remonte le nœud `<video>` et redémarre la lecture.
- Un aperçu qui échoue se dégrade en `st.caption`. Le bandeau rouge est réservé à
  ce qui empêche réellement de continuer — il emporterait aussi le reste de la page.
- Les valeurs des widgets sont déjà figées quand le script s'exécute : `if
  st.button(...)` suffit, inutile d'ajouter un drapeau en session.
- `st.empty` est le seul conteneur qu'on puisse vider ; un `st.container` ne se
  reprend pas.

## Fichiers temporaires

MoviePy et ffmpeg travaillent sur des chemins réels : tout upload et tout GIF est
un fichier temporaire. Chacun a un propriétaire unique qui l'efface — la page
d'accueil pour la vidéo importée, le cache pour les GIFs produits. Introduire un
fichier temporaire sans désigner qui le supprime, c'est introduire une fuite.

## Validation numérique

Toute grandeur venue d'un widget ou d'un conteneur passe par les validateurs de
`utils/MathsVerif.py` avant d'être utilisée : `nan` traverse `min` et `max` sans
être borné et empoisonne silencieusement tout ce qui suit.
